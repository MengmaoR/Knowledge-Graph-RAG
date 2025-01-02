import py2neo
from entityRecognition import entity_recognition_with_model, get_entity_types
from intentRecognition import intent_recognition_with_model, get_relationship_types
from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage

API_KEY = "sk-AYjPnVCKzpm79mAxjjg8kU38baXdoMC1G7xYcmECW41mE14m"
API_URL = "https://xiaoai.plus/v1/"

# Function to create the language model instance
def create_model(temperature: float, streaming: bool = False):
    return ChatOpenAI(
        openai_api_key=API_KEY,
        openai_api_base=API_URL,
        temperature=temperature,
        model_name="gpt-4o-mini",
        streaming=streaming,
    )

# Create the language model
model = create_model(temperature=0.8, streaming=False)

class RAGProcessor:
    def __init__(self, neo4j_uri, neo4j_user, neo4j_password):
        self.client = py2neo.Graph(neo4j_uri, user=neo4j_user, password=neo4j_password)

    def generate_cypher_query(self, origin_nodes, intent_relationship):
        """
        生成Cypher查询语句，根据起源节点和意图关系获取相关节点。
        """
        # 替换中文逗号为英文逗号并处理多个关系类型
        if isinstance(intent_relationship, str):
            intent_relationship = intent_relationship.replace("，", ",").split(",")
        
        # 转换为 Neo4j 的语法格式
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

    def write_to_file(self, file_path, content):
        """
        将内容写入文件。
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                file.writelines([line + '\n' for line in content])
        except Exception as e:
            print(f"写入文件 {file_path} 失败：{e}")

    def generate_answer(self, user_prompt, context_data):
        """
        使用GPT模型生成基于上下文的回答。
        """
        context = "相关知识点包括: " + ", ".join(
            {f"{data['relationship_type']} -> {data['connected_node']}" for data in context_data}
        )
        full_prompt = f"{context}\n\n用户问题: {user_prompt}\n回答:"
        print("Full Prompt："+full_prompt)

        try:
            response = model.invoke(full_prompt)
            if isinstance(response, AIMessage):
                return response.content.strip()
            return "抱歉，我无法生成回答。"
        except Exception as e:
            print("生成回答失败：", e)
            return "抱歉，我无法生成回答。"

def main():
    # 配置Neo4j连接参数
    # 此参数为医疗知识图谱
    neo4j_uri = "neo4j+s://26ec9262.databases.neo4j.io"
    neo4j_user = "neo4j"
    neo4j_password = "HRd_pRCk7IF3bC624Ih20jaQ-wLUXmGPLUg_FzGGVOM"

    rag_processor = RAGProcessor(neo4j_uri, neo4j_user, neo4j_password)
    try:
        rag_processor.client.run("MATCH (n) RETURN n LIMIT 1")
        print("成功连接到Neo4j数据库。")
    except Exception as e:
        print(f"连接Neo4j数据库失败：{e}")

    # 获取实体和关系类型
    entity_types = get_entity_types(rag_processor.client)
    relationship_types = get_relationship_types(rag_processor.client)

    # 用户输入
    user_question = "怎么知道我有没有糖尿病？"

    # 实体识别
    entity_types_recognized, entity_names_recognized = entity_recognition_with_model(user_question, entity_types, rag_processor.client)

    if not entity_names_recognized:
        print("未能识别出有效的实体。")
        return

    # 写入实体识别结果到 node_file.txt
    node_file = "node_file.txt"
    rag_processor.write_to_file(node_file, entity_names_recognized)

    # 意图识别
    intent = intent_recognition_with_model(user_question, relationship_types)

    if not intent:
        print("未能识别出有效的意图。")
        return
    
    # 如果意图中包含多个关系类型，用列表传递
    intent_relationships = intent.replace("，", ",").split(",") if "," in intent else [intent]

    # 写入意图识别结果到 link_file.txt
    link_file = "link_file.txt"
    rag_processor.write_to_file(link_file, intent_relationships)

    # 生成查询语句
    queries = rag_processor.generate_cypher_query(entity_names_recognized, intent_relationships)

    # 写入生成的查询语句到 cypher_file.txt
    cypher_file = "cypher_file.txt"
    rag_processor.write_to_file(cypher_file, queries)

    # 执行查询
    query_results = rag_processor.execute_queries(queries)

    # 检查查询结果并写入到文件
    result_file = "result_file.txt"
    if query_results:
        formatted_results = [
            f"Connected Node: {result['connected_node']}, Relationship Type: {result['relationship_type']}"
            for result in query_results
        ]
        rag_processor.write_to_file(result_file, formatted_results)
    else:
        print("未找到相关的连接节点。")
        rag_processor.write_to_file(result_file, ["未找到相关的连接节点。"])

    # 调用大模型生成回答
    answer = rag_processor.generate_answer(user_question, query_results)

    # 输出回答
    print("回答:", answer)

if __name__ == "__main__":
    main()
