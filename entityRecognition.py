import py2neo
from langchain.schema import AIMessage

def get_entity_types(client):
    """
    获取Neo4j中所有实体类型
    """
    entity_types = []
    result = client.run("MATCH (n) RETURN DISTINCT labels(n) AS labels")
    for record in result:
        entity_types.extend(record["labels"])

    return list(set(entity_types))

def find_entity_type_in_neo4j(client, entity_name):
    """
    从Neo4j中查找实体类型
    """
    query = f"MATCH (n) WHERE any(prop in keys(n) WHERE n[prop] = '{entity_name}') RETURN labels(n) AS labels"
    result = client.run(query)
    for record in result:
        return record["labels"]
    return None

def entity_recognition_with_model(question, entity_types, client, model, response_placeholder):
    response_placeholder.text("正在进行实体识别... 0.0")
    
    """
    使用GPT-4 API进行实体识别，将问题中的关键实体匹配到Neo4j的实体类型中。
    如果未能在Neo4j中找到实体类型，则使用模型从已知实体类型中选择最合适的类型。
    """
    examples = """
    所有实体类型：
    疾病，药品，食物，疾病症状
    问题："感冒后需要吃什么药？"
    输出：
    实体类型：疾病
    实体名称：感冒

    所有实体类型：
    大洲，国家，城市，机场，航线
    问题："从北京飞往莫斯科的航班有哪些？"
    输出：
    实体类型：城市，城市
    实体名称：北京，莫斯科
    """

    prompt = f"""
    你现在连接到了一个Neo4j知识图谱, 以下是其中的所有实体类型:
    {', '.join(entity_types)}。

    我将提供给你一个问题，你需要根据以上给出的实体类型，识别问题中的实体，并匹配到对应的实体类型（必须为知识图谱中存在的实体类型）中。以下是一些示例：
    {examples}

    现在请根据以下问题识别实体：
    输入问题："{question}"
    输出格式：
    实体类型：类型1, 类型2, ...
    实体名称：名称1, 名称2, ...
    你需要严格按照输出格式进行输出，禁止输出其他任何内容，如果无法识别实体，请不要输出。
    """
    response = model.invoke(prompt)  # 调用 GPT-4 模型
    if response is None:
        print("模型返回了空响应。")
        return None, None
    if isinstance(response, AIMessage):
        response = response.content  # 提取 AIMessage 中的内容
    print("实体识别模型答复：", response)
        
    response_placeholder.text("正在进行实体识别... 0.1")

    # 输出内容解析
    lines = response.split("\n")
    entity_names = []

    for line in lines:
        entity_names = [item.strip() for item in line.replace("实体名称：", "").replace("，", ",").replace("\'", "").split(",")]

    # 语义扩展
    expanded_entities = []
    for entity_name in entity_names:
        expanded = semantic_expansion(entity_name, model)
        expanded_entities.extend(expanded)
    
    entity_names.extend(expanded_entities)
    
    response_placeholder.text("正在进行实体识别... 0.2")

    # 翻译为英文
    english_entity_names = []
    for entity_name in entity_names:
        english = translate_to_english([entity_name], model)
        english_entity_names.extend(english)

    entity_names.extend(english_entity_names)
    
    response_placeholder.text("正在进行实体识别... 0.3")

    final_types = []
    print("全部实体类型：", entity_types)
    print("识别的实体：", entity_names)
    for entity in entity_names:
        neo4j_type = find_entity_type_in_neo4j(client, entity)
        if neo4j_type:
            final_types.append(neo4j_type[0])  # 使用Neo4j中返回的实体类型
        else:
            # 如果Neo4j中未找到实体类型，调用模型选择最合适的实体类型
            selection_prompt = f"""
            在以下实体类型中选择最适合实体"{entity}"的类型，要求必须为以下实体类型之一：
            {', '.join(entity_types)}
            输出格式：类型
            """
            selected_type_response = model.invoke(selection_prompt)
            if isinstance(selected_type_response, AIMessage):
                selected_type_response = selected_type_response.content.strip()
            final_types.append(selected_type_response)
            
    response_placeholder.text("正在进行实体识别... 0.4")

    return final_types, entity_names

def semantic_expansion(entity_name, model):
    """
    使用GPT-4 API对识别出的实体进行语义扩展。
    """
    prompt = f"""
    对以下实体进行语义扩展，提供与此实体含义完全一致的专业术语或专业词汇，对每个实体只能提供一个扩展，禁止提供多个扩展：
    实体：{entity_name}
    请严格按照以下格式输出：
    <扩展实体1>, <扩展实体2>, ...
    你需要严格按照输出格式进行输出，禁止输出其他任何内容，如果无需要扩展的实体，则不要输出。
    """
    response = model.invoke(prompt)
    if isinstance(response, AIMessage):
        response = response.content  # 提取 AIMessage 中的内容
    expanded_entities = [e.strip() for e in response.replace("，", ",").replace("\'", "").split(",") if e.strip()]
    
    return expanded_entities

def translate_to_english(entity_names, model):
    """
    使用GPT-4 API将中文实体名称翻译为英文。
    """
    prompt = f"""
    将以下中文实体名称翻译为英文：
    {', '.join(entity_names)}
    请严格按照以下格式输出：
    <英文实体1>, <英文实体2>, ...
    你需要严格按照输出格式进行输出，禁止输出其他任何内容，如果无需要翻译的内容，则不要输出。
    """
    response = model.invoke(prompt)
    if isinstance(response, AIMessage):
        response = response.content  # 提取 AIMessage 中的内容
    english_entity_names = [e.strip() for e in response.replace("，", ",").replace("\'", "").split(",") if e.strip()]
    return english_entity_names

def main():
    # 连接 Neo4j 数据库
    client = py2neo.Graph('neo4j+s://7151d126.databases.neo4j.io', user='neo4j', password='MyK4DmqZDhWWGy18FItMZWFlpins1PWDTVTZZLFm2cQ')
    # 获取实体类型
    entity_types = get_entity_types(client)
    print("知识图谱中的实体类型：", entity_types)

    # 用户输入
    question = "怎么从北京去上海？"

    # 实体识别
    entity_types_recognized, entity_names_recognized = entity_recognition_with_model(question, entity_types, client)
    if entity_types_recognized and entity_names_recognized:
        print(f"识别的实体类型：{', '.join(entity_types_recognized)}")
        print(f"识别的具体实体：{', '.join(entity_names_recognized)}")
    else:
        print("未能识别出有效的实体。")

if __name__ == "__main__":
    main()
