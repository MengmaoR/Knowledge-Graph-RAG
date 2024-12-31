# 导入必要的库
from neo4j import GraphDatabase
import openai
import os

class Neo4jConnector:
    def __init__(self, uri, user, password, node_file, link_file):
        """
        初始化函数，连接到Neo4j数据库，并打开node.txt和link.txt文件。
        
        :param uri: Neo4j数据库URI
        :param user: 数据库用户名
        :param password: 数据库密码
        :param node_file: 节点文件路径
        :param link_file: 连接类型文件路径
        """
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            print("成功连接到Neo4j数据库。")
        except Exception as e:
            print("连接到Neo4j数据库失败：", e)
            raise e

        # 读取节点名称
        try:
            with open(node_file, 'r', encoding='utf-8') as nf:
                self.initial_nodes = [line.strip() for line in nf if line.strip()]
            print(f"读取了 {len(self.initial_nodes)} 个初始节点。")
        except Exception as e:
            print("读取node.txt文件失败：", e)
            raise e

        # 读取连接类型
        try:
            with open(link_file, 'r', encoding='utf-8') as lf:
                self.link_types = [line.strip() for line in lf if line.strip()]
            print(f"读取了 {len(self.link_types)} 种连接类型。")
        except Exception as e:
            print("读取link.txt文件失败：", e)
            raise e

    def close(self):
        """关闭数据库连接。"""
        self.driver.close()
        print("关闭了Neo4j数据库连接。")

    def search_connected_nodes(self):
        """
        从Neo4j中查找与初始节点通过指定连接类型相连的所有节点，
        并将结果保存在一个向量中。
        
        :return: 包含初始节点和其连接节点的列表
        """
        connected_nodes = []
        with self.driver.session() as session:
            for node in self.initial_nodes:
                for link in self.link_types:
                    cypher_query = f"""
                    MATCH (n:Node {{name: $node_name}})-[:{link}]->(m)
                    RETURN m.name AS connected_node
                    """
                    try:
                        result = session.run(cypher_query, node_name=node)
                        for record in result:
                            connected_node = record["connected_node"]
                            connected_nodes.append((node, connected_node))
                    except Exception as e:
                        print(f"执行Cypher查询失败：{e}")
        print(f"总共找到 {len(connected_nodes)} 条连接。")
        return connected_nodes

class LargeModelQA:
    def __init__(self, api_key):
        """
        初始化大模型问答函数，设置OpenAI API密钥。
        
        :param api_key: OpenAI API密钥
        """
        openai.api_key = api_key

    def generate_answer(self, prompt, context_nodes):
        """
        生成回答，将节点名称作为上下文提示。
        
        :param prompt: 用户提问的提示
        :param context_nodes: 节点名称的列表
        :return: 生成的回答
        """
        # 将节点名称拼接成字符串，作为上下文
        context = "相关知识点包括: " + ", ".join(set([node for pair in context_nodes for node in pair]))
        
        # 完整的提示
        full_prompt = f"{context}\n\n用户问题: {prompt}\n回答:"

        try:
            response = openai.Completion.create(
                engine="text-davinci-003",  # 根据需要选择模型
                prompt=full_prompt,
                max_tokens=500,
                temperature=0.7,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0
            )
            answer = response.choices[0].text.strip()
            return answer
        except Exception as e:
            print("生成回答失败：", e)
            return "抱歉，我无法生成回答。"

def main():
    # 配置Neo4j连接参数
    neo4j_uri = "bolt://localhost:7687"  # 根据实际情况修改
    neo4j_user = "neo4j"                 # 根据实际情况修改
    neo4j_password = "password"          # 根据实际情况修改
    node_file = "node.txt"
    link_file = "link.txt"

    # 配置OpenAI API密钥
    openai_api_key = os.getenv("OPENAI_API_KEY")  # 推荐使用环境变量存储密钥
    if not openai_api_key:
        openai_api_key = input("请输入您的OpenAI API密钥: ")

    # 初始化Neo4j连接
    connector = Neo4jConnector(neo4j_uri, neo4j_user, neo4j_password, node_file, link_file)

    # 执行查询
    connected_nodes = connector.search_connected_nodes()

    # 关闭Neo4j连接
    connector.close()

    # 初始化大模型问答
    qa = LargeModelQA(openai_api_key)

    while True:
        user_prompt = input("请输入您的问题（输入'退出'结束）：")
        if user_prompt.lower() == '退出':
            print("结束程序。")
            break
        answer = qa.generate_answer(user_prompt, connected_nodes)
        print("回答:", answer)

if __name__ == "__main__":
    main()