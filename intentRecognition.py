import py2neo
from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage

def get_graph_structure(client):
    """
    获取Neo4j中的图结构，包括节点和关系。
    """
    graph_structure = ""
    graph_structure += "所有节点类型：\n"
    result = client.run("CALL db.labels()")
    for record in result:
        graph_structure += f"{record['label']}, "

    graph_structure += "\n所有关系类型：\n"
    result = client.run("CALL db.relationshipTypes()")
    for record in result:
        graph_structure += f"{record['relationshipType']}, "
    
    graph_structure += "\n节点连接关系：\n"
    result = client.run("""
        MATCH (n)-[r]->(m)
        RETURN DISTINCT labels(n) AS from_node, labels(m) AS to_node, type(r) AS relationship
    """)
    for record in result:
        from_node = record['from_node'][0] if record['from_node'] else "Unknown"
        to_node = record['to_node'][0] if record['to_node'] else "Unknown"
        relationship = record['relationship']
        graph_structure += f"{from_node} - {relationship} -> {to_node})\n"

    return graph_structure

def get_relationship_types(client):
    """
    获取Neo4j中所有关系类型
    """
    relationship_types = []
    result = client.run("MATCH ()-[r]->() RETURN DISTINCT type(r) AS relationship")
    for record in result:
        relationship_types.append(record["relationship"])

    return relationship_types

def intent_recognition_with_model(question, relationship_types, graph_structure, node_types, model):
    """
    使用GPT-4 API进行意图识别，判断问题中包含的关系类型。
    """
    examples = """
    所有关系类型：
    疾病症状，疾病常用药品，疾病宜吃食物，疾病忌吃食物，疾病治疗方法
    问题："我现在感觉头晕和胃疼，该吃什么才能好？"
    意图：疾病症状，疾病常用药品，疾病宜吃食物

    所有关系类型：
    IN_REGION, IN_COUNTRY, IN_CITY, HAS_ROUTE, COMPANY_NAME, FLIGHT_TIME
    问题："我现在在亚洲旅游，希望后续去美国，有什么推荐的航班？"
    意图：IN_REGION, IN_COUNTRY, IN_CITY, HAS_ROUTE
    """

    prompt = f"""
    你现在连接到了一个Neo4j知识图谱，我将提供给你一个问题，你需要根据知识图谱的结构和关系类型进行逻辑推理，找出所有对解答问题有帮助的关系类型.

    以下是此知识图谱的结构：
    {graph_structure}

    以下从此问题中提取的所有节点类型，你需要通过推理确保提取出的关系可以将这些节点连接起来：
    {', '.join(node_types)}

    以下是所有关系类型，你必须严格从这其中进行选择，禁止回答任何其他语句：
    {', '.join(relationship_types)}

    问题："{question}"
    输出格式：意图：关系1, 关系2, ...
    你需要严格按照输出格式进行输出，禁止输出其他任何内容，如果无法识别意图，请不要输出。
    """

    response = model.invoke(prompt)  # 调用 GPT-4 模型
    if response is None:
        print("模型返回了空响应。")
        return None
    if isinstance(response, AIMessage):
        response = response.content.strip()  # 提取 AIMessage 中的内容并去除多余空白

    # 提取意图
    if response.startswith("意图："):
        intent = response.replace("意图：", "").replace("，", ",").strip()
        print("意图识别结果：", intent)
        return intent

    print("模型返回的格式不正确：", response)
    return None

def main():
    # 连接 Neo4j 数据库
    client = py2neo.Graph('neo4j+s://7151d126.databases.neo4j.io', user='neo4j', password='MyK4DmqZDhWWGy18FItMZWFlpins1PWDTVTZZLFm2cQ')

    # 获取关系类型
    graph_structure = get_graph_structure(client)
    relationship_types = get_relationship_types(client)
    print("Neo4j中的关系类型：", relationship_types)

    # 用户输入
    question = "我希望2月11号从北京飞去多哈，有什么推荐的航线，需要转机吗？"

    # 意图识别
    intent = intent_recognition_with_model(question, relationship_types, graph_structure)
    if intent:
        print(f"识别的意图：{intent}")
    else:
        print("未能识别出有效的意图。")

if __name__ == "__main__":
    main()
