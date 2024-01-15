import openai
import os
import json
import streamlit as st
from dotenv import load_dotenv
from docx import Document

load_dotenv()

openai.api_key = os.environ.get("OPEN_API_KEY")
openai.api_base = "https://tensora-oai-france.openai.azure.com/"
openai.api_type = "azure"
openai.api_version = "2023-12-01-preview"

def extract_text_from_word(file_path):
    doc = Document(file_path)
    text = ""

    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"

    return text

def create_analyses(i: int,json_model, data_sources):
    system_prompt = "You receive a question from a user asking for data from a document or multiple documents. Please extract the exact data from the user question out of the document(s). Return your answers in the form of this example JSON Objekt: "+json_model+". Do not use the values provided by the example data model and provide precise values to the given keys. Datasource(s) to extract from: "
    for source in data_sources:
        file_text = extract_text_from_word(f"test_cases/{source['folder_name']}/{i+1}.docx")
        system_prompt += f"{source['prompt_name']}: {file_text}, "
    try:
        res = openai.ChatCompletion.create(
                    engine="gpt-4-1106",
                    # deployment_id="gpt-4",
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
    return f"Results from CV nr {i+1}: \n"+res["choices"][0]["message"]["content"]+"\n\n"

if "data_model" not in st.session_state:
    st.session_state["data_model"] = None

col1, col2 = st.columns([2, 1])

col1.title("Document analyzer")
col2.image("phx_logo.svg")

# st.write("Please select the documents to be used as data sources.")

st.multiselect("Please select the document folders to be used as data sources.",["CVs","Letter of motivations"], key="folder_options")

if len(st.session_state["folder_options"])>0:
    st.text_input("Enter the prompt regarding the data to be extracted from the documents",placeholder="E.g.: give me the names and dates of birth of the candidate",key="prompt")
    st.write("If you are satisfied with the prompt, click on 'Generate' to create the data model.")
    if st.button("Generate"):
        if len(st.session_state["prompt"])>0:
            with st.spinner("Generating the data model..."):
                try:
                    res = openai.ChatCompletion.create(
                        engine="gpt-4-1106",
                        # deployment_id="gpt-4",
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
    data_model_json_string = st.session_state["data_model"][st.session_state["data_model"].find("{"):st.session_state["data_model"].rfind("}")+1]
    data_model_json = json.loads(data_model_json_string)
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
            amount_files_for_iteration = len(os.listdir("test_cases/cvs"))
            result_string = ""
            data_sources = []
            for folder in st.session_state["folder_options"]:
                if folder == "CVs":
                    data_sources.append({"folder_name":"cvs","prompt_name":"CV"})
                elif folder == "Letter of motivations":
                    data_sources.append({"folder_name":"letters","prompt_name":"Letter of motivation"})
            progress_bar = st.progress(0,text="Creating the analyses for each candidate...")
            for i in range(amount_files_for_iteration):
                result_string += create_analyses(i,st.session_state["data_model"],data_sources)
                print(100//amount_files_for_iteration)
                progress_bar.progress((100//amount_files_for_iteration)*(i+1))
            with open("results.txt", "w") as file:
                file.write(result_string)
        st.success("The results have been compiled. Look in the 'results.txt' file")
        
    
    
    