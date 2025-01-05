# Knowledge Graph RAG Project

## Environment Setup

Execute the following commands to install the required dependencies. If you don't have a conda environment, please skip the first two steps:

```bash
# Create and activate conda environment (optional)
conda create --name kg_env python=3.10
conda activate kg_env

# Install dependencies
pip install -r requirements.txt
```

## Run the Project

Execute the following command to run the project:

```bash
python -m streamlit run webui.py --server.port 8501
```

Then, you can visit the website at: [http://localhost:8501](http://localhost:8501)

## Build a Neo4j Knowledge Graph for Test

1. **Create a Neo4j Instance**  
   Please register and create an instance on the Neo4j official website: [Neo4j Official Site](https://neo4j.com/). After creating the instance, retrieve the URI, username, and password information.

2. **Modify the Connection Information**  
   Open the `create_knowledge_graph.py` file and locate the following code snippet:

   ```python
   class KnowledgeGraphMaker(object):
       def __init__(self):
           uri = "neo4j+s://51e1b91b.databases.neo4j.io"  # Replace with your Neo4j instance URI
           user = "neo4j"  # Replace with your Neo4j instance username
           password = "ZaVV51il4LJkBzQHwy_oqTBX5-tHSNYay0Zids63zc8"  # Replace with your Neo4j instance password
           self.driver = GraphDatabase.driver(uri, auth=(user, password))
   ```

   Replace `uri`, `user`, and `password` with the information from your Neo4j instance.

   And you may need to change some of the code in the `create_knowledge_graph.py` file to match the data you have.

3. **Run the Script**  
   After modifying the connection information, run the following command to build the knowledge graph:

   ```bash
   python create_knowledge_graph.py
   ```

   Please note that building the knowledge graph may take some time, depending on the data size and system performance.
