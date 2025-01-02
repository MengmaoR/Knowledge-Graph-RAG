import py2neo
from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage
import logging

API_KEY = "sk-AYjPnVCKzpm79mAxjjg8kU38baXdoMC1G7xYcmECW41mE14m"
API_URL = "https://xiaoai.plus/v1/"

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
entity_logger = logging.getLogger("EntityRecognition")
intent_logger = logging.getLogger("IntentRecognition")
query_logger = logging.getLogger("QueryResults")

entity_handler = logging.FileHandler("entity_recognition.log")
intent_handler = logging.FileHandler("intent_recognition.log")
query_handler = logging.FileHandler("query_results.log")

entity_logger.addHandler(entity_handler)
intent_logger.addHandler(intent_handler)
query_logger.addHandler(query_handler)

# Function to create the language model instance
def create_model(temperature: float, streaming: bool = False):
    return ChatOpenAI(
        openai_api_key=API_KEY,
        openai_api_base=API_URL,
        temperature=temperature,
        model_name="gpt-4o-mini",
        streaming=streaming,
    )

model = create_model(temperature=0.8, streaming=False)

def get_entity_types(client):
    entity_types = []
    result = client.run("MATCH (n) RETURN DISTINCT labels(n) AS labels")
    for record in result:
        entity_types.extend(record["labels"])
    return list(set(entity_types))

def find_entity_type_in_neo4j(client, entity_name):
    query = f"MATCH (n) WHERE n.名称 = '{entity_name}' RETURN labels(n) AS labels"
    result = client.run(query)
    for record in result:
        return record["labels"]
    return None

def entity_recognition_with_model(question, entity_types, client):
    examples = """
    示例：
    问题："感冒后需要吃什么药？"
    输出：
    实体类型：疾病
    实体名称：感冒
    """
    prompt = f"""
    你是一个智能助手，帮助识别问题中的实体并与以下Neo4j实体类型匹配：
    {', '.join(entity_types)}。

    {examples}

    输入问题："{question}"
    输出格式：
    实体类型：类型1, 类型2, ...
    实体名称：名称1, 名称2, ...
    """
    response = model.invoke(prompt)
    if response and isinstance(response, AIMessage):
        response = response.content
    else:
        entity_logger.info("实体识别失败，模型返回了空响应或错误格式。")
        return None, None

    lines = response.split("\n")
    entity_types = []
    entity_names = []
    for line in lines:
        if line.startswith("实体类型："):
            entity_types = [item.strip() for item in line.replace("实体类型：", "").split(",")]
        elif line.startswith("实体名称："):
            entity_names = [item.strip() for item in line.replace("实体名称：", "").split(",")]

    final_types = []
    for entity in entity_names:
        neo4j_type = find_entity_type_in_neo4j(client, entity)
        if neo4j_type:
            final_types.append(neo4j_type[0])
        else:
            selection_prompt = f"""
            在以下实体类型中选择最适合实体"{entity}"的类型：
            {', '.join(entity_types)}
            输出格式：类型
            """
            selected_type_response = model.invoke(selection_prompt)
            if isinstance(selected_type_response, AIMessage):
                selected_type_response = selected_type_response.content.strip()
            final_types.append(selected_type_response)

    entity_logger.info(f"问题：{question}\n实体类型：{final_types}\n实体名称：{entity_names}")
    return final_types, entity_names

def get_relationship_types(client):
    relationship_types = []
    result = client.run("MATCH ()-[r]->() RETURN DISTINCT type(r) AS relationship")
    for record in result:
        relationship_types.append(record["relationship"])
    return relationship_types

def intent_recognition_with_model(question, relationship_types):
    examples = """
    示例：
    问题："感冒了可以吃西红柿鸡蛋汤吗？"
    意图：疾病宜吃食物
    """
    prompt = f"""
    你是一个智能助手，帮助识别问题的意图。
    在以下关系类型中选择最贴近问题的意图：
    {', '.join(relationship_types)}。

    {examples}

    输入问题："{question}"
    输出格式：意图：关系类型
    """
    response = model.invoke(prompt)
    if response and isinstance(response, AIMessage):
        response_content = response.content.strip()
        if response_content.startswith("意图："):
            intent = response_content.replace("意图：", "").strip()
            intent_logger.info(f"问题：{question}\n意图：{intent}")
            return intent
    intent_logger.info(f"意图识别失败，模型返回：{response}")
    return None

def generate_query(entities, intent):
    cypher_queries = []
    for entity in entities:
        query = f"""
        MATCH (n)-[r:{intent}]->(m)
        WHERE n.名称 = '{entity}'
        RETURN r, m
        """
        cypher_queries.append(query)
    query_logger.info(f"生成的查询语句：{cypher_queries}")
    return cypher_queries

def main():
    client = py2neo.Graph("bolt://localhost:7687", auth=("neo4j", "12345678"))
    question = input("请输入您的问题：")

    entity_types = get_entity_types(client)
    entity_types_recognized, entities_recognized = entity_recognition_with_model(question, entity_types, client)
    if not entities_recognized:
        print("未能识别出有效的实体。")
        return

    relationship_types = get_relationship_types(client)
    intent = intent_recognition_with_model(question, relationship_types)
    if not intent:
        print("未能识别出有效的意图。")
        return

    queries = generate_query(entities_recognized, intent)
    print("生成的查询语句：", queries)

if __name__ == "__main__":
    main()
