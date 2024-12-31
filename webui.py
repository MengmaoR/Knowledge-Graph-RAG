import os
import streamlit as st
# import ner_model as zwk
import pickle
import ollama
from transformers import BertTokenizer
import torch
import py2neo
import random
import re

from langchain_openai import ChatOpenAI

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


llm = None

@st.cache_resource
def load_model(model_name):
    global llm
    llm = create_model(temperature=0.8, streaming=True, model_name=model_name)
    
    return None,None,None,None,None,None,None,None

def Intent_Recognition(query, choice):
    prompt = f"""
阅读下列提示，回答问题（问题在输入的最后）:
请识别用户问题中关于医疗药物方面的的查询意图。

问题输入："{query}"
"""
    # rec_result = ollama.generate(model=choice, prompt=prompt)['response'] # lifang535 delete
    rec_result = llm.predict(prompt) # lifang535 add
    print(f'意图识别结果:{rec_result}')
    return rec_result
    # response, _ = glm_model.chat(glm_tokenizer, prompt, history=[])
    # return response

def generate_prompt(intent, query):
    # entities = zwk.get_ner_result(bert_model, bert_tokenizer, query, rule, tfidf_r, device, idx2tag)
    entities = {}
    # print(intent)
    # print(entities)
    yitu = []
    # prompt = "<指令>你是一个医疗问答机器人，你需要根据给定的提示回答用户的问题。请注意，你的全部回答必须完全基于给定的提示，不可自由发挥。如果根据提示无法给出答案，立刻回答“根据已知信息无法回答该问题”。</指令>"
    # prompt +="<指令>请你仅针对医疗类问题提供简洁和专业的回答。如果问题不是医疗相关的，你一定要回答“我只能回答医疗相关的问题。”，以明确告知你的回答限制。</指令>"
    
    prompt = "<指令>你是一个医疗问答机器人，你需要根据给定的提示回答用户的问题。</指令>"

    prompt += f"<用户>{query}</用户>"
    prompt += f"<用户意图>{intent}</用户意图>"

    return prompt,"、".join(yitu),entities

# def ans_stream(prompt):
#     result = ""
#     for res,his in glm_model.stream_chat(glm_tokenizer, prompt, history=[]):
#         yield res

def main(is_admin, usname):
    # cache_model = 'best_roberta_rnn_model_ent_aug' # lifang535 delete
    model_name = 'gpt-4o-mini' # lifang535 add
    st.title(f"医疗智能问答机器人")

    with st.sidebar:
        col1, col2 = st.columns([0.6, 0.6])
        with col1:
            # st.image(os.path.join("img", "logo.jpg"), use_column_width=True) # lifang535 delete
            st.image(os.path.join("img", "logo.jpg"), use_container_width=True) # lifang535 add

        st.caption(
            f"""<p align="left">欢迎您，{'管理员' if is_admin else '用户'}{usname}！当前版本：{1.0}</p>""",
            unsafe_allow_html=True,
        )

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
            options=['Qwen 1.5', 'Llama2-Chinese']
        )
        choice = 'qwen:32b' if selected_option == 'Qwen 1.5' else 'llama2-chinese:13b-chat-q8_0'

        show_ent = show_int = show_prompt = False
        if is_admin:
            show_ent = st.sidebar.checkbox("显示实体识别结果")
            show_int = st.sidebar.checkbox("显示意图识别结果")
            show_prompt = st.sidebar.checkbox("显示查询的知识库信息")
            if st.button('修改知识图谱'):
            # 显示一个链接，用户可以点击这个链接在新标签页中打开百度
                st.markdown('[点击这里修改知识图谱](http://127.0.0.1:7474/)', unsafe_allow_html=True)

        if st.button("返回登录"):
            st.session_state.logged_in = False
            st.session_state.admin = False
            # st.experimental_rerun() # lifang535 delete
            st.rerun() # lifang535 add

    load_model(model_name)
    # client = py2neo.Graph('http://localhost:7474', user='neo4j', password='wei8kang7.long', name='neo4j') # lifang535 delete

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

        query = current_messages[-1]["content"]
        response = Intent_Recognition(query, choice)
        response_placeholder.empty()

        prompt, yitu, entities = generate_prompt(response, query)

        # last = "" # lifang535 delete: 流式回答，更丝滑
        # for chunk in ollama.chat(model=choice, messages=[{'role': 'user', 'content': prompt}], stream=True): # lifang535 delete
        #     last += chunk['message']['content'] # lifang535 delete
        #     response_placeholder.markdown(last) # lifang535 delete
        last = llm.predict(prompt) # lifang535 add
        response_placeholder.markdown(last) # lifang535 add
        response_placeholder.markdown("")

        knowledge = re.findall(r'<提示>(.*?)</提示>', prompt)
        zhishiku_content = "\n".join([f"提示{idx + 1}, {kn}" for idx, kn in enumerate(knowledge) if len(kn) >= 3])
        with st.chat_message("assistant"):
            st.markdown(last)
            if show_ent:
                with st.expander("实体识别结果"):
                    st.write(str(entities))
            if show_int:
                with st.expander("意图识别结果"):
                    st.write(yitu)
            if show_prompt:
                
                
                with st.expander("点击显示知识库信息"):
                    st.write(zhishiku_content)
        current_messages.append({"role": "assistant", "content": last, "yitu": yitu, "prompt": zhishiku_content, "ent": str(entities)})


    st.session_state.messages[active_window_index] = current_messages
