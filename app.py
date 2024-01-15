import openai
import os
import json
import io
from datetime import datetime
import streamlit as st
import pandas as pd
from azure.storage.blob import BlobServiceClient, ContainerClient
from dotenv import load_dotenv
from docx import Document

load_dotenv()

openai.api_key = os.environ.get("OPEN_API_KEY")
openai.api_base = os.environ.get("OPEN_API_BASE")
openai.api_type = os.environ.get("OPEN_API_TYPE")
openai.api_version = os.environ.get("OPEN_API_VERSION")

def extract_text_from_word(blob_content):
    bytes_io = io.BytesIO(blob_content)
    doc = Document(bytes_io)
    text = ""

    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"

    return text

def create_analyses(i: int,json_model, data_sources):
    system_prompt = "You receive a question from a user asking for data from a document or multiple documents. Please extract the exact data from the user question out of the document(s). Return your answers in the form of this example JSON Objekt: "+json_model+". Do not use the values provided by the example data model and provide precise values to the given keys. Datasource(s) to extract from: "
    for source in data_sources:
        blob_data = get_blob_content(f'{os.environ.get("USE_CASE_FOLDER")}/{source["folder_name"]}/{i+1}.docx')
        file_text = extract_text_from_word(blob_data)
        system_prompt += f"{source['prompt_name']}: {file_text}, "
    try:
        res = openai.ChatCompletion.create(
                    # engine="gpt-35-turbo",
                    deployment_id="aaai-gpt",
                    temperature=0.1,
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt,
                        },
                        {
                            "role": "user",
                            "content": st.session_state["prompt"],
                        },
                    ],
                )
    except Exception as e: 
        print(f"Fehler beim erstellen der analyse von CV {i}: {str(e)}")
        st.error("Something went wrong, please contact the site admin.", icon="🚨")
        return ""
    print(f"Results from CV nr {i+1}: \n"+res["choices"][0]["message"]["content"]+"\n")
    return res["choices"][0]["message"]["content"]+"\n\n"

def get_blob_subfolder(amount_subfolder: bool):
    blob_service_client = BlobServiceClient.from_connection_string(os.environ.get("BLOB_STORAGE_CONNECTION_STRING"))
    container_client = blob_service_client.get_container_client(os.environ.get("CONTAINER_NAME"))
    subfolders = set()
    if amount_subfolder:
        first_subfolder = list(container_client.list_blob_names(name_starts_with=os.environ.get("USE_CASE_FOLDER")))[0].split("/")[1]
        for blob_name in container_client.list_blob_names(name_starts_with=os.environ.get("USE_CASE_FOLDER")+"/"+first_subfolder):
            blob_path_parts = blob_name.split('/')
            if len(blob_path_parts) > 2:
                subfolders.add(blob_name)
    else:
        for blob_name in container_client.list_blob_names(name_starts_with=os.environ.get("USE_CASE_FOLDER")):
            blob_path_parts = blob_name.split('/')
            if len(blob_path_parts) > 2:
                subfolders.add(blob_path_parts[1])
    return list(subfolders)

def get_blob_content(blob_name):
    blob_service_client = BlobServiceClient.from_connection_string(os.environ.get("BLOB_STORAGE_CONNECTION_STRING"))
    container_client = blob_service_client.get_container_client(os.environ.get("CONTAINER_NAME"))
    blob_data = container_client.get_blob_client(blob_name).download_blob()
    file_content = blob_data.readall()
    return file_content

def extract_json_from_string(json_string: str):
    data_json_string = json_string[json_string.find("{"):json_string.rfind("}")+1]
    data_json = json.loads(data_json_string)
    return data_json

if "data_model" not in st.session_state:
    st.session_state["data_model"] = None
if "multiselect_choices" not in st.session_state:
    st.session_state["multiselect_choices"] = get_blob_subfolder(False)

col1, col2 = st.columns([2, 1])

col1.title("Document analyzer")
col2.image("phx_logo.svg")

# st.write("Please select the documents to be used as data sources.")

st.multiselect("Please select the document folders to be used as data sources.",st.session_state["multiselect_choices"], key="folder_options")

if len(st.session_state["folder_options"])>0:
    st.text_input("Enter the prompt regarding the data to be extracted from the documents",placeholder="E.g.: give me the names and dates of birth of the candidate",key="prompt")
    st.write("If you are satisfied with the prompt, click on 'Generate' to create the data model.")
    if st.button("Generate"):
        if len(st.session_state["prompt"])>0:
            with st.spinner("Generating the data model..."):
                try:
                    res = openai.ChatCompletion.create(
                        # engine="gpt-35-turbo",
                        deployment_id="aaai-gpt",
                        temperature=0.1,
                        messages=[
                            {
                                "role": "system",
                                "content": "You receive a question from a user asking for data from documents. Please restructure the data to be extracted from the question into a JSON object, generate the keys and insert example values. Keep it as simple as it is asked by the user in the prompt, dont make it complicated. Do not make nested objects. In the next step, this model is then used iteratively for different entities. The model should only ever represent one entity, e.g. a candidate, contract or policy."
                            },
                            {
                                "role": "user",
                                "content": st.session_state["prompt"],
                            },
                        ],
                    )
                    print(res["choices"][0]["message"]["content"])
                    st.session_state["data_model"] = res["choices"][0]["message"]["content"]
                    st.rerun()
                except Exception as e: 
                    print(f"Fehler beim erstellen des Datenmodels: {str(e)}")
                    st.error("Something went wrong, please contact the site admin.", icon="🚨")
        else:
            st.warning("Please enter your prompt.")
if st.session_state["data_model"]:
    data_model_json = extract_json_from_string(st.session_state["data_model"])
    write_string = "The output excel file would be structured as follows:\n\nThese are the columns of the Excel file with the corresponding example values:\n\n"
    table_columns = list(data_model_json.keys())
    table_values = list(data_model_json.values())
    # for i,key in enumerate(data_model_json.keys()):
    #     write_string += f"Column {i+1}:\n\n{key} (example value: {data_model_json[key]})\n\n"
    st.write(write_string)
    st.table({table_columns[i]: [table_values[i]] for i in range(len(table_columns))})
    st.write("If you are satisfied with this output, then press 'Accept', otherwise, adjust the prompt and press 'Generate' again")
    if st.button("Accept"):
        with st.spinner("Creating the analyses..."):
            amount_files_for_iteration = len(get_blob_subfolder(True))
            data_sources = []
            for folder in st.session_state["folder_options"]:
                data_sources.append({"folder_name":folder,"prompt_name":folder})
            progress_bar = st.progress(0,text="Creating the analyses for each candidate...")
            json_results = []
            for i in range(amount_files_for_iteration):
                result = create_analyses(i,st.session_state["data_model"],data_sources)
                json_results.append(extract_json_from_string(result))
                progress_bar.progress((100//amount_files_for_iteration)*(i+1))
            df = pd.DataFrame(json_results)
            excel_bytes = io.BytesIO()
            df.to_excel(excel_bytes, index=False)
            blob_service_client = BlobServiceClient.from_connection_string(os.environ.get("BLOB_STORAGE_CONNECTION_STRING"))
            container_client = blob_service_client.get_container_client(os.environ.get("CONTAINER_NAME"))
            container_client.upload_blob(name=f"results/results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", data=excel_bytes.getvalue(), overwrite=True)
        st.success("The results have been compiled. Please look in the 'results' folder of the blob storage.")
        
    
    
    