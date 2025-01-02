import os
import streamlit as st
import pickle
import ollama
from transformers import BertTokenizer
import torch
import py2neo
import random
import re

from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage
from entityRecognition import entity_recognition_with_model, get_entity_types
from intentRecognition import intent_recognition_with_model, get_relationship_types

API_KEY = "sk-AYjPnVCKzpm79mAxjjg8kU38baXdoMC1G7xYcmECW41mE14m"
API_URL = "https://xiaoai.plus/v1/"

# Function to create the language model instance
def create_model(temperature: float, streaming: bool = False, model_name: str = "gpt-4o-mini"):
    return ChatOpenAI(
        openai_api_key=API_KEY,
        openai_api_base=API_URL,
        temperature=temperature,
        model_name=model_name,
        streaming=streaming,
    )

@st.cache_resource
def load_model(model_name):
    llm = create_model(temperature=0.8, streaming=True, model_name=model_name)
    print(f"[load_model] llm: {llm}")
    return llm

class RAGProcessor:
    def __init__(self, neo4j_uri, neo4j_user, neo4j_password):
        self.client = py2neo.Graph(neo4j_uri, user=neo4j_user, password=neo4j_password)

    def generate_cypher_query(self, origin_nodes, intent_relationship):
        """
        生成Cypher查询语句，根据起源节点和意图关系获取相关节点。
        """
        if isinstance(intent_relationship, str):
            intent_relationship = intent_relationship.replace("，", ",").split(",")
        
        relationships = "|".join(f"{rel.strip()}" for rel in intent_relationship)

        queries = []
        for node in origin_nodes:
            query = f"""
            MATCH (n)-[r:{relationships}]->(m)
            WHERE n.名称 = '{node}'
            RETURN m.名称 AS connected_node, type(r) AS relationship_type
            """
            queries.append(query)

            query = f"""
            MATCH (n)-[r:{relationships}]->(m)
            WHERE m.名称 = '{node}'
            RETURN n.名称 AS connected_node, type(r) AS relationship_type
            """
            queries.append(query)
        return queries

    def execute_queries(self, queries):
        """
        执行Cypher查询，并返回结果。
        """
        results = []
        for query in queries:
            try:
                result = self.client.run(query)
                for record in result:
                    results.append({
                        "connected_node": record["connected_node"],
                        "relationship_type": record["relationship_type"]
                    })
            except Exception as e:
                print(f"执行Cypher查询失败：{e}")
        return results

    def generate_answer(self, llm, user_prompt, context_data):
        """
        使用GPT模型生成基于上下文的回答。
        """
        context = "相关知识点包括: " + ", ".join(
            {f"{data['relationship_type']} -> {data['connected_node']}" for data in context_data}
        )
        full_prompt = f"{context}\n\n用户问题: {user_prompt}\n回答:"
        print("Full Prompt："+full_prompt)

        try:
            response = llm.invoke(full_prompt)
            return response.content.strip() if isinstance(response, AIMessage) else "抱歉，我无法生成回答。"
        except Exception as e:
            print("生成回答失败：", e)
            return "抱歉，我无法生成回答。"

# Function for intent recognition
def Intent_Recognition(query, choice, rag_processor, llm):
    print(f"[Intent_Recognition] llm: {llm}")
    
    prompt = f"""
    阅读下列提示，回答问题（问题在输入的最后）:
    请识别用户问题中关于医疗药物方面的的查询意图。

    问题输入："{query}"
    """
    
    rec_result = llm.predict(prompt)
    print(f'意图识别结果:{rec_result}')

    # RAG Processing: Retrieve relevant knowledge from Neo4j based on the recognized intent
    entity_types = get_entity_types(rag_processor.client)
    relationship_types = get_relationship_types(rag_processor.client)

    # Entity recognition
    entity_types_recognized, entity_names_recognized = entity_recognition_with_model(query, entity_types, rag_processor.client)

    if not entity_names_recognized:
        print("未能识别出有效的实体。")
        return rec_result, []

    # Intent recognition
    intent = intent_recognition_with_model(query, relationship_types)

    if not intent:
        print("未能识别出有效的意图。")
        return rec_result, []

    # Generate RAG queries
    intent_relationships = intent.replace("，", ",").split(",") if "," in intent else [intent]
    queries = rag_processor.generate_cypher_query(entity_names_recognized, intent_relationships)
    query_results = rag_processor.execute_queries(queries)

    return rec_result, query_results

# Generate prompt for the LLM
def generate_prompt(intent, query, query_results):
    entities = {}
    yitu = []
    prompt = "<指令>你是一个医疗问答机器人，你需要根据给定的提示回答用户的问题。</指令>"
    prompt += f"<用户>{query}</用户>"
    prompt += f"<用户意图>{intent}</用户意图>"

    # Formatting the results from the RAG process
    context_data = "\n".join(
        [f"{result['relationship_type']} -> {result['connected_node']}" for result in query_results]
    )

    return prompt, context_data, entities

def main():
    # Neo4j connection configuration (change to your actual Neo4j details)
    neo4j_uri = "neo4j+s://26ec9262.databases.neo4j.io"
    neo4j_user = "neo4j"
    neo4j_password = "HRd_pRCk7IF3bC624Ih20jaQ-wLUXmGPLUg_FzGGVOM"

    # Initialize RAGProcessor
    rag_processor = RAGProcessor(neo4j_uri, neo4j_user, neo4j_password)

    llm = load_model('gpt-4o-mini')
    st.title(f"医疗智能问答机器人")

    with st.sidebar:
        col1, col2 = st.columns([0.6, 0.6])
        with col1:
            st.image(os.path.join("ui_img", "logo.jpg"), use_container_width=True)

        if 'chat_windows' not in st.session_state:
            st.session_state.chat_windows = [[]]
            st.session_state.messages = [[]]

        if st.button('新建对话窗口'):
            st.session_state.chat_windows.append([])
            st.session_state.messages.append([])

        window_options = [f"对话窗口 {i + 1}" for i in range(len(st.session_state.chat_windows))]
        selected_window = st.selectbox('请选择对话窗口:', window_options)
        active_window_index = int(selected_window.split()[1]) - 1

        selected_option = st.selectbox(
            label='请选择大语言模型:',
            options=['GPT-4o', 'GPT-4o mini'],
        )
        choice = 'gpt-4o' if selected_option == 'GPT-4o' else 'gpt-4o-mini'

        show_ent = show_int = show_prompt = False
        show_ent = st.sidebar.checkbox("显示实体识别结果")
        show_int = st.sidebar.checkbox("显示意图识别结果")
        show_prompt = st.sidebar.checkbox("显示查询的知识库信息")

    current_messages = st.session_state.messages[active_window_index]

    for message in current_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                if show_ent:
                    with st.expander("实体识别结果"):
                        st.write(message.get("ent", ""))
                if show_int:
                    with st.expander("意图识别结果"):
                        st.write(message.get("yitu", ""))
                if show_prompt:
                    with st.expander("点击显示知识库信息"):
                        st.write(message.get("prompt", ""))

    if query := st.chat_input("Ask me anything!", key=f"chat_input_{active_window_index}"):
        current_messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)

        response_placeholder = st.empty()
        response_placeholder.text("正在进行意图识别...")

        # Process RAG logic and generate answer
        query = current_messages[-1]["content"]
        rec_result, query_results = Intent_Recognition(query, choice, rag_processor, llm)

        response_placeholder.empty()

        prompt, context_data, _ = generate_prompt(rec_result, query, query_results)

        # Generate the response from the model
        # last = llm.predict(prompt) # lifang535 delete
        last = rag_processor.generate_answer(llm, query, query_results) # lifang535 add
        response_placeholder.markdown(last)
        response_placeholder.markdown("")

        knowledge = re.findall(r'<提示>(.*?)</提示>', prompt)
        zhishiku_content = "\n".join([f"提示{idx + 1}, {kn}" for idx, kn in enumerate(knowledge) if len(kn) >= 3])

        with st.chat_message("assistant"):
            st.markdown(last)
            if show_ent:
                with st.expander("实体识别结果"):
                    st.write(str({}))  # Add actual entities here
            if show_int:
                with st.expander("意图识别结果"):
                    st.write(rec_result)
            if show_prompt:
                with st.expander("点击显示知识库信息"):
                    st.write(zhishiku_content)

        current_messages.append({"role": "assistant", "content": last, "yitu": rec_result, "prompt": zhishiku_content, "ent": str({})})

    st.session_state.messages[active_window_index] = current_messages

if __name__ == "__main__":
    main()
