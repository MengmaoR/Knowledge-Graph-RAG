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
from intentRecognition import intent_recognition_with_model, get_relationship_types, get_graph_structure
import gen_answer as gen

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
    rag_processor = gen.RAGProcessor(neo4j_uri, neo4j_user, neo4j_password)

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

        show_ent = st.sidebar.checkbox("显示实体识别结果", value=True)
        show_int = st.sidebar.checkbox("显示意图识别结果", value=True)
        show_prompt = st.sidebar.checkbox("显示查询的知识库信息", value=True)
        deep_search = st.sidebar.checkbox("深度搜索", value=False)
        if deep_search:
            epoch = st.sidebar.number_input("搜索迭代次数", value=1)

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

    if question := st.chat_input("Ask me anything!", key=f"chat_input_{active_window_index}"):
        current_messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        response_placeholder = st.empty()

        # 获取实体和关系类型
        entity_types = get_entity_types(rag_processor.client)
        relationship_types = get_relationship_types(rag_processor.client)
        
        # 实体识别
        response_placeholder.text("正在进行实体识别...")
        entity_types_recognized, entity_names_recognized = entity_recognition_with_model(question, entity_types, rag_processor.client)
        if not entity_names_recognized:
            print("未能识别出有效的实体。")
            return
        
        # 写入实体识别结果到 node_file.txt
        node_file = "node_file.txt"
        rag_processor.write_to_file(node_file, entity_names_recognized)
        enti = entity_names_recognized
        print(f"识别的实体：{enti}")

        # 意图识别
        response_placeholder.text("正在进行意图识别...")
        graph_structure = get_graph_structure(rag_processor.client)
        intent = intent_recognition_with_model(question, relationship_types, graph_structure, entity_types_recognized)
        if not intent:
            print("未能识别出有效的意图。")
            return
        
        # 如果意图中包含多个关系类型，用列表传递
        intent_relationships = intent.replace("，", ",").split(",") if "," in intent else [intent]
        inte = intent

        # 写入意图识别结果到 link_file.txt
        link_file = "link_file.txt"
        rag_processor.write_to_file(link_file, intent_relationships)

        # 生成查询语句
        queries = rag_processor.generate_cypher_query(entity_names_recognized, intent_relationships)

        # 写入生成的查询语句到 cypher_file.txt
        cypher_file = "cypher_file.txt"
        rag_processor.write_to_file(cypher_file, queries)

        # 执行查询
        query_results, new_origin_nodes = rag_processor.execute_queries(queries, entity_names_recognized)
        print("查询结果：", query_results)

        # 深度搜索（可选）
        if deep_search:
            query_results += rag_processor.depth_search(new_origin_nodes, epoch)

        # 检查查询结果并写入到文件
        prompt = []
        result_file = "result_file.txt"
        if query_results:
            formatted_results = [
                f"{result['origin_node']} - {result['relationship_type']} -> {result['connected_node']}"
                for result in query_results
            ]
            prompt.append(formatted_results)
            rag_processor.write_to_file(result_file, formatted_results)
        else:
            print("未找到相关的连接节点。")
            rag_processor.write_to_file(result_file, ["未找到相关的连接节点。"])

        # 调用大模型生成回答
        answer = rag_processor.generate_answer(question, query_results)

        # 输出回答
        print("回答:", answer)
    
        response_placeholder.markdown(answer)
        response_placeholder.markdown("")

        with st.chat_message("assistant"):
            st.markdown(answer)
            if show_ent:
                with st.expander("实体识别结果"):
                    st.write(enti)
            if show_int:
                with st.expander("意图识别结果"):
                    st.write(inte)
            if show_prompt:
                with st.expander("点击显示知识库信息"):
                    st.write(prompt)

        current_messages.append({"role": "assistant", "content": answer, "yitu": intent, "prompt": prompt, "ent": str({})})

    st.session_state.messages[active_window_index] = current_messages

if __name__ == "__main__":
    main()
