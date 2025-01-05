import json
from neo4j import GraphDatabase

def process_data(paths):
    diseases = []
    for path in paths:
        disease_data = open(path, 'r', encoding='UTF-8').readlines()
        for data in disease_data:
            disease = json.loads(data)
            diseases.append(disease)
    return diseases

def output_data(data, filepath, jieba_mode=False):
    with open(filepath, 'w', encoding='UTF-8') as file:
        for line in data:
            line = line.strip(' \n\r\"')
            if jieba_mode:
                line += ' 18000 nz'
            line += '\n'
            file.write(line)

class GraphMaker(object):
    def __init__(self):
        uri = "neo4j+s://51e1b91b.databases.neo4j.io"
        user = "neo4j"
        password = "ZaVV51il4LJkBzQHwy_oqTBX5-tHSNYay0Zids63zc8"
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def extract_data(self, diseases_dict):
        data = dict()

        depts = []
        drugs = []
        symptoms = []
        foods = []
        disease_names = []

        symptom_rel = []
        neopathy_rel = []
        dept_rel = []
        disease_cat_rel = []
        disease_drug_rel = []
        not_eat_rel = []
        can_eat_rel = []

        for disease in diseases_dict:
            disease_name = disease['name']
            disease_names.append(disease_name)

            if 'drug' in disease:
                drugs += disease['drug']
                for drug in disease['drug']:
                    disease_drug_rel.append([disease_name, drug])

            if 'cure_dept' in disease:
                dept = disease['cure_dept']
                depts += disease['cure_dept']
                if len(dept) == 2:
                    big, small = dept[0], dept[1]
                    dept_rel.append([small, big])
                    disease_cat_rel.append([disease_name, small])
                elif len(dept) == 1:
                    disease_cat_rel.append([disease_name, dept[0]])

            if 'symptom' in disease:
                symptoms += disease['symptom']
                for symptom in disease['symptom']:
                    symptom_rel.append([disease_name, symptom])

            if 'neopathy' in disease:
                for neopathy in disease['neopathy']:
                    neopathy_rel.append([disease_name, neopathy])

            if 'can_eat' in disease:
                foods += disease['can_eat']
                for can_eat in disease['can_eat']:
                    can_eat_rel.append([disease_name, can_eat])

            if 'not_eat' in disease:
                foods += disease['not_eat']
                for not_eat in disease['not_eat']:
                    not_eat_rel.append([disease_name, not_eat])

            if 'get_prob' not in disease:
                disease['get_prob'] = '无数据'

            if 'treat_period' not in disease:
                disease['treat_period'] = '无数据'

            if 'treat_cost' not in disease:
                disease['treat_cost'] = '无数据'

            if 'get_way' not in disease:
                disease['get_way'] = '无数据'

        data['diseases'] = diseases_dict
        data['disease_names'] = disease_names
        data['depts'] = set(depts)
        data['drugs'] = set(drugs)
        data['symptoms'] = set(symptoms)
        data['foods'] = set(foods)
        data['symptom_rel'] = symptom_rel
        data['neopathy_rel'] = neopathy_rel
        data['dept_rel'] = dept_rel
        data['disease_cat_rel'] = disease_cat_rel
        data['disease_drug_rel'] = disease_drug_rel
        data['not_eat_rel'] = not_eat_rel
        data['can_eat_rel'] = can_eat_rel
        return data

    def make_disease_nodes(self, diseases_dict):
        i = 1
        for disease in diseases_dict:
            if i % 50 == 0:
                print("create disease node count=%d" % i)
            query = """
            CREATE (d:Disease {name: $name, intro: $intro, cause: $cause, prevent: $prevent, 
                                nursing: $nursing, insurance: $insurance, easy_get: $easy_get, 
                                get_way: $get_way, get_prob: $get_prob, treat: $treat, treat_prob: $treat_prob, 
                                treat_period: $treat_period, treat_cost: $treat_cost, treat_detail: $treat_detail})
            """
            params = {
                "name": disease['name'],
                "intro": disease['intro'],
                "cause": disease['cause'],
                "prevent": disease['prevent'],
                "nursing": disease['nursing'],
                "insurance": disease['insurance'],
                "easy_get": disease['easy_get'],
                "get_way": disease['get_way'],
                "get_prob": disease['get_prob'],
                "treat": disease['treat'],
                "treat_prob": disease['treat_prob'],
                "treat_period": disease['treat_period'],
                "treat_cost": disease['treat_cost'],
                "treat_detail": disease['treat_detail']
            }
            with self.driver.session() as session:
                session.run(query, params)
            i += 1
        print("create total disease node count=%d" % (i - 1))

    def make_nodes(self, data):
        self.make_disease_nodes(data['diseases'])
        self.create_nodes("Department", data['depts'])
        self.create_nodes("Drug", data['drugs'])
        self.create_nodes("Symptom", data['symptoms'])
        self.create_nodes("Food", data['foods'])

    def make_rels(self, data):
        self.create_rels("Disease", "Disease", data['neopathy_rel'], "has_neopathy", "有并发症")
        self.create_rels("Disease", "Symptom", data['symptom_rel'], "has_symptom", "有症状")
        self.create_rels("Disease", "Drug", data['disease_drug_rel'], "can_use_drug", "可以用药")
        self.create_rels("Department", "Department", data['dept_rel'], "belongs_to", "属于")
        self.create_rels("Disease", "Department", data['disease_cat_rel'], "belongs_to", "属于")
        self.create_rels("Disease", "Food", data['can_eat_rel'], "can_eat", "可以吃")
        self.create_rels("Disease", "Food", data['not_eat_rel'], "not_eat", "不能吃")

    def create_nodes(self, label, entities_names):
        for entity in entities_names:
            query = f"CREATE (n:{label} {{name: $name}})"
            params = {"name": entity}
            with self.driver.session() as session:
                session.run(query, params)

    def create_rels(self, start_label, end_label, rels, rel_type, name):
        for start, end in rels:
            query = f"""
            MATCH (p:{start_label}), (q:{end_label}) 
            WHERE p.name = $start AND q.name = $end
            CREATE (p)-[r:{rel_type} {{name: $name}}]->(q)
            """
            params = {"start": start, "end": end, "name": name}
            with self.driver.session() as session:
                session.run(query, params)


if __name__ == '__main__':
    graph_maker = GraphMaker()

    diseases_dict = process_data(['./data/medical.json'])
    data = graph_maker.extract_data(diseases_dict)

    graph_maker.make_nodes(data)
    graph_maker.make_rels(data)
