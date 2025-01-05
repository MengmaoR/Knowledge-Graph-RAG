import os
import streamlit as st

from langchain_openai import ChatOpenAI
from entityRecognition import entity_recognition_with_model, get_entity_types
from intentRecognition import intent_recognition_with_model, get_relationship_types, get_graph_structure
import gen_answer as gen

API_KEY = "sk-AYjPnVCKzpm79mAxjjg8kU38baXdoMC1G7xYcmECW41mE14m"
API_URL = "https://xiaoai.plus/v1/"

MEDICAL_NEO4J_URI = "neo4j+s://26ec9262.databases.neo4j.io"
MEDICAL_NEO4J_USER = "neo4j"
MEDICAL_NEO4J_PASSWORD = "HRd_pRCk7IF3bC624Ih20jaQ-wLUXmGPLUg_FzGGVOM"

FLIGHT_NEO4J_URI = "neo4j+s://7151d126.databases.neo4j.io"
FLIGHT_NEO4J_USER = "neo4j"
FLIGHT_NEO4J_PASSWORD = "MyK4DmqZDhWWGy18FItMZWFlpins1PWDTVTZZLFm2cQ"

# Function to create the language model instance
def create_model(temperature: float, streaming: bool = False, model_name: str = "gpt-4o-mini"):
    return ChatOpenAI(
        openai_api_key=API_KEY,
        openai_api_base=API_URL,
        temperature=temperature,
        model_name=model_name,
        streaming=streaming,
    )

# Load the language model
llm = create_model(temperature=0.5, streaming=True, model_name="gpt-4o-mini")

@st.cache_resource
def load_model(model_name):
    llm = create_model(temperature=0.5, streaming=True, model_name=model_name)
    print(f"[load_model] llm: {llm}")
    return llm

def show_message(current_messages, show_ent, show_int, show_prompt):
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

def main():
    if 'active_window_index' not in st.session_state:
        st.session_state.active_window_index = 0
    
    if 'chat_windows' not in st.session_state:
        st.session_state.chat_windows = [[]]
        
    if 'messages' not in st.session_state:
        st.session_state.messages = [[]]
        
    if 'rag_processors' not in st.session_state:
        st.session_state.rag_processors = [gen.RAGProcessor(MEDICAL_NEO4J_URI, MEDICAL_NEO4J_USER, MEDICAL_NEO4J_PASSWORD)]

    if 'title' not in st.session_state:
        st.session_state.title = ["医疗智能问答机器人"]
        
    if 'database_option_indexes' not in st.session_state:
        st.session_state.database_option_indexes = [0]
        
    if 'new_window' not in st.session_state:
        st.session_state.new_window = False
        
    # Initialize RAGProcessor
    rag_processor = st.session_state.rag_processors[st.session_state.active_window_index]

    llm = load_model('gpt-4o-mini')
    # st.title(f"医疗智能问答机器人")
    
    database_options = ['医疗信息知识图谱']

    with st.sidebar:
        col1, col2 = st.columns([0.6, 0.6])
        with col1:
            st.image(os.path.join("ui_img", "logo.jpg"), use_container_width=True, output_format="PNG")
            st.markdown(
                """
                <style>
                img {
                    border-radius: 15%;
                }
                </style>
                """,
                unsafe_allow_html=True
            )

        if st.button('新建对话窗口'):
            st.session_state.new_window = True
            
            st.session_state.chat_windows.append([])
            st.session_state.messages.append([])
            st.session_state.rag_processors.append(gen.RAGProcessor(MEDICAL_NEO4J_URI, MEDICAL_NEO4J_USER, MEDICAL_NEO4J_PASSWORD)) # TODO: Add RAGProcessor
            st.session_state.title.append("医疗智能问答机器人") # TODO: titles
            st.session_state.database_option_indexes.append(0)
            
            st.session_state.active_window_index = len(st.session_state.chat_windows) - 1
            
        window_options = [f"对话窗口 {i + 1}" for i in range(len(st.session_state.chat_windows))]

        # if st.session_state.new_window:
        selected_window = st.selectbox('请选择对话窗口:', window_options, index=len(st.session_state.chat_windows) - 1)
        # else:
        #     selected_window = st.selectbox('请选择对话窗口:', window_options)

        if st.session_state.active_window_index != int(selected_window.split()[1]) - 1:
            # print(f"[st.session_state.new_window = False]")
            st.session_state.new_window = False
        
        st.session_state.active_window_index = int(selected_window.split()[1]) - 1

        rag_processor = st.session_state.rag_processors[st.session_state.active_window_index]

    if st.session_state.new_window:
        database_option = st.selectbox(
            label='请选择知识图谱:',
            options=['医疗信息知识图谱', '航班信息知识图谱', '自定义知识图谱'],
            index=st.session_state.database_option_indexes[st.session_state.active_window_index],
        )

        if database_option == '医疗信息知识图谱':
            rag_processor = gen.RAGProcessor(MEDICAL_NEO4J_URI, MEDICAL_NEO4J_USER, MEDICAL_NEO4J_PASSWORD)
            st.session_state.rag_processors[st.session_state.active_window_index] = rag_processor
            st.session_state.title[st.session_state.active_window_index] = "医疗智能问答机器人"
            st.session_state.database_option_indexes[st.session_state.active_window_index] = 0
        elif database_option == '航班信息知识图谱':
            rag_processor = gen.RAGProcessor(FLIGHT_NEO4J_URI, FLIGHT_NEO4J_USER, FLIGHT_NEO4J_PASSWORD)
            st.session_state.rag_processors[st.session_state.active_window_index] = rag_processor
            st.session_state.title[st.session_state.active_window_index] = "航班智能问答机器人"
            st.session_state.database_option_indexes[st.session_state.active_window_index] = 1
        elif database_option == '自定义知识图谱':
            neo4j_uri = st.text_input("请输入 Neo4j 数据库 URI:")
            neo4j_user = st.text_input("请输入 Neo4j 数据库用户名:")
            neo4j_password = st.text_input("请输入 Neo4j 数据库密码:", type="password")
            # 确定按钮
            if st.button("连接到 Neo4j 数据库"):
                try:
                    rag_processor = gen.RAGProcessor(neo4j_uri, neo4j_user, neo4j_password)
                    st.session_state.rag_processors[st.session_state.active_window_index] = rag_processor
                    st.session_state.title[st.session_state.active_window_index] = "自定义智能问答机器人"
                    st.session_state.database_option_indexes[st.session_state.active_window_index] = 2
                    rag_processor.client.run("MATCH (n) RETURN n LIMIT 1")
                    st.text(f"连接 Neo4j 数据库成功！")
                except Exception as e:
                    st.text(f"连接 Neo4j 数据库失败：{e}")
        else:
            pass
    
    st.title(st.session_state.title[st.session_state.active_window_index])

    with st.sidebar:
        selected_option = st.selectbox(
            label='请选择大语言模型:',
            options=['GPT-4o mini', 'GPT-4o'],
        )
        choice = 'gpt-4o' if selected_option == 'GPT-4o' else 'gpt-4o-mini'

        show_ent = st.sidebar.checkbox("显示实体识别结果", value=True)
        show_int = st.sidebar.checkbox("显示意图识别结果", value=True)
        show_prompt = st.sidebar.checkbox("显示查询的知识库信息", value=True)
        deep_search = st.sidebar.checkbox("深度搜索(*)", value=False)
        if deep_search:
            epoch = st.sidebar.number_input("搜索迭代次数", value=1)
            expend_origin = st.sidebar.checkbox("扩展搜索节点", value=False)
        if deep_search == False:
            st.sidebar.text("*深度搜索可以提供更全面和丰富的回答，但可能大幅增加查询时间。")
        if deep_search:
            st.sidebar.text("*扩展搜索节点选项应只对规模较小，或节点间连接关系松散的知识图谱使用，否则可能导致查询时间过长或查询结果过长，无法生成回答。")


    current_messages = st.session_state.messages[st.session_state.active_window_index]
    
    show_message(current_messages, show_ent, show_int, show_prompt)
    
    if question := st.chat_input("Ask me anything!", key=f"chat_input_{st.session_state.active_window_index}"):
        st.session_state.new_window = False
        # TODO: 数据库选择界面去除
        
        print(f"用户问题：{question}")
        current_messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        # st.session_state.messages[st.session_state.active_window_index] = current_messages_copy
        
        response_placeholder = st.empty()
        st.empty()

        # 获取实体和关系类型
        entity_types = get_entity_types(rag_processor.client)
        relationship_types = get_relationship_types(rag_processor.client)
        
        # 实体识别
        response_placeholder.text("正在进行实体识别...")
        entity_types_recognized, entity_names_recognized = entity_recognition_with_model(question, entity_types, rag_processor.client, llm, response_placeholder)
        response_placeholder.text("正在进行实体识别... 1")
        if not entity_names_recognized:
            print("未能识别出有效的实体。")
            return
        
        response_placeholder.text("正在进行实体识别... 2")
        
        # 写入实体识别结果到 node_file.txt
        node_file = "node_file.txt"
        rag_processor.write_to_file(node_file, entity_names_recognized)
        
        response_placeholder.text("正在进行实体识别... 3")

        enti = entity_names_recognized

        # 意图识别
        response_placeholder.text("正在进行意图识别...")
        graph_structure = get_graph_structure(rag_processor.client)
        
        response_placeholder.text("正在进行意图识别... 1")
        
        intent = intent_recognition_with_model(question, relationship_types, graph_structure, entity_types_recognized, llm)
        
        response_placeholder.text("正在进行意图识别... 2")
        
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
        response_placeholder.text("正在检索知识图谱...")
        queries = rag_processor.generate_cypher_query(entity_names_recognized, intent_relationships)

        # 执行查询
        query_results, new_origin_nodes = rag_processor.execute_queries(queries, entity_names_recognized)

        # 深度搜索（可选）
        if deep_search:
            response_placeholder.text("正在执行深度搜索...")
            if expend_origin:
                print("扩展后起始节点:", new_origin_nodes)
                query_results += rag_processor.depth_search(new_origin_nodes, epoch)
            else:
                query_results += rag_processor.depth_search(entity_names_recognized, epoch)

        # 写入生成的查询语句到 cypher_file.txt
        cypher_file = "cypher_file.txt"
        rag_processor.write_to_file(cypher_file, queries)

        # 检查查询结果并写入到文件
        knowledge = []
        result_file = "result_file.txt"
        if query_results:
            formatted_results = [
                f"{result['id']}: {result['origin_node']} - {result['relationship_type']} -> {result['connected_node']}"
                for result in query_results
            ]
            knowledge.append(formatted_results)
            rag_processor.write_to_file(result_file, formatted_results)
        else:
            print("未找到相关的连接节点。")
            rag_processor.write_to_file(result_file, ["未找到相关的连接节点。"])

        # 调用大模型生成回答
        response_placeholder.text("正在生成回答...")
        title = st.session_state.title[st.session_state.active_window_index]
        answer = rag_processor.generate_answer(question, knowledge, graph_structure, enti, inte, title, llm)

        # 输出回答
        if answer is not None:
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
                        st.write(knowledge)
        else:
            st.empty()

        current_messages.append({"role": "assistant", "content": answer, "yitu": inte, "prompt": knowledge, "ent": enti})

    st.session_state.messages[st.session_state.active_window_index] = current_messages

if __name__ == "__main__":
    main()
