import py2neo
from entityRecognition import entity_recognition_with_model, get_entity_types
from intentRecognition import intent_recognition_with_model, get_relationship_types, get_graph_structure
from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage

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
            WHERE any(prop in keys(n) WHERE n[prop] = '{node}')
            RETURN apoc.map.fromPairs([key in keys(m)[..5] | [key, m[key]]]) AS m_limited_properties, 
                   type(r) AS relationship_type
            """
            queries.append(query)

            query = f"""
            MATCH (n)-[r:{relationships}]->(m)
            WHERE any(prop in keys(m) WHERE m[prop] = '{node}')
            RETURN apoc.map.fromPairs([key in keys(n)[..5] | [key, n[key]]]) AS n_limited_properties, 
                   type(r) AS relationship_type
            """
            queries.append(query)
        return queries

    def execute_queries(self, queries, origin_nodes):
        """
        执行Cypher查询，并返回结果。
        """
        results = []
        new_origin_nodes = origin_nodes.copy()
        for index, query in enumerate(queries):
            try:
                result = self.client.run(query)
                for record in result:
                    # if record["m_limited_properties"]:
                    # 如果 record 中包含 m_limited_properties 这个键
                    if record.get("m_limited_properties"):
                        print(record)
                        results.append({
                            "origin_node": origin_nodes[index // 2],
                            "relationship_type": record["relationship_type"],
                            "connected_node": record["m_limited_properties"],
                        })
                        new_origin_nodes.append(record["m_limited_properties"].get(0))
                    # elif record["n_limited_properties"]:
                    elif record.get("n_limited_properties"):
                        results.append({
                            "origin_node": record["n_limited_properties"],
                            "relationship_type": record["relationship_type"],
                            "connected_node": origin_nodes[index // 2],
                        })
                        new_origin_nodes.append(record["n_limited_properties"].get(0))
            except Exception as e:
                print(f"执行Cypher查询失败：{e}")
                continue

        return results, new_origin_nodes
    
    def depth_search(self, origin_nodes, epoch=1):
        results = []
        for _ in range(epoch):
            queries = []
            for node in origin_nodes:
                query = f"""
                MATCH (n)-[r]->(m)
                WHERE any(prop in keys(n) WHERE n[prop] = '{node}')
                RETURN apoc.map.fromPairs([key in keys(m)[..5] | [key, m[key]]]) AS m_limited_properties, 
                    type(r) AS relationship_type
                """
                queries.append(query)

                query = f"""
                MATCH (n)-[r]->(m)
                WHERE any(prop in keys(m) WHERE m[prop] = '{node}')
                RETURN apoc.map.fromPairs([key in keys(n)[..5] | [key, n[key]]]) AS n_limited_properties, 
                    type(r) AS relationship_type
                """
                queries.append(query)
            result, origin_nodes = self.execute_queries(queries, origin_nodes)
            results.extend(result)
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

    def generate_answer(self, user_prompt, context_data, enti, inte, title, model):
        """
        使用GPT模型生成基于上下文的回答。
        """
        full_prompt = f"""
        你是一个{title}，你现在连接到了一个知识图谱，后续将提供给你一个问题，以下是关于该问题你可能运用到的所有相关信息：\n
        {context_data}\n

        为了丰富回答内容，你需要使回答涵盖每种关系类型下的查询信息，同时将重点关注于实体识别结果和意图识别结果。
        实体识别结果: \n{enti}\n
        意图识别结果: \n{inte}\n

        下面将给出用户的问题，请你严格根据前面给出的信息进行推理和回答，在回答过程中严禁使用任何其余知识和信息，如果前面给出的信息不足以回答用户的问题，请直接告知用户你无法回答。
        用户问题: {user_prompt}\n

        你的回答必须保持严谨和专业，对于每一行回答，你都必须列举出知识信息作为佐证，所有知识信息必须处理为易于理解的自然语言描述再进行输出，如果无法列出佐证，则不要回答。
        回答:
        """
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

    # 此参数为航班知识图谱
    # neo4j_uri = "neo4j+s://7151d126.databases.neo4j.io"
    # neo4j_user = "neo4j"
    # neo4j_password = "MyK4DmqZDhWWGy18FItMZWFlpins1PWDTVTZZLFm2cQ"

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
    user_question = "我一直肚子疼，怎么才能好起来？"
    # user_question = "我现在在中国，这个假期想去日本东京旅行，从哪里出发比较好？"

    # 实体识别
    entity_types_recognized, entity_names_recognized = entity_recognition_with_model(user_question, entity_types, rag_processor.client)

    if not entity_names_recognized:
        print("未能识别出有效的实体。")
        return

    # 写入实体识别结果到 node_file.txt
    node_file = "node_file.txt"
    rag_processor.write_to_file(node_file, entity_names_recognized)

    # 意图识别
    graph_structure = get_graph_structure(rag_processor.client)
    intent = intent_recognition_with_model(user_question, relationship_types, graph_structure, entity_types_recognized)

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
    query_results, new_origin_nodes = rag_processor.execute_queries(queries, entity_names_recognized)
    print("查询结果：", query_results)

    # 深度搜索（可选）
    query_results += rag_processor.depth_search(new_origin_nodes, epoch=0)

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
    answer = rag_processor.generate_answer(user_question, prompt, entity_names_recognized, intent)

    # 输出回答
    print("回答:", answer)

if __name__ == "__main__":
    main()
