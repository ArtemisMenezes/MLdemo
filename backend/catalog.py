"""Constantes compartilhadas: catálogo de CNAEs, UFs, estágios e ICP padrão."""
from datetime import date

REF_DATE = date(2026, 11, 1)  

# código, descrição, proporção aproximada na base
CNAES = [
    ("6201-5/00", "Desenvolvimento de software sob encomenda", 0.12),
    ("6204-0/00", "Consultoria em tecnologia da informação", 0.12),
    ("7020-4/00", "Consultoria em gestão empresarial", 0.14),
    ("7311-4/00", "Agências de publicidade", 0.10),
    ("8630-5/04", "Atividade odontológica", 0.12),
    ("4120-4/00", "Construção de edifícios", 0.12),
    ("5611-2/01", "Restaurantes e similares", 0.20),
    ("8599-6/04", "Treinamento em desenvolvimento profissional", 0.08),
]
TI_CNAES = {"6201-5/00", "6204-0/00"}

UF_WEIGHTS = {"SP": .24, "MG": .10, "RJ": .09, "BA": .09, "CE": .08, "PR": .07, "PE": .07,
              "RS": .06, "SC": .05, "MA": .04, "RN": .03, "PB": .03}
NORDESTE = {"CE", "PE", "BA", "RN", "PB", "MA"}
CITIES = {
    "SP": ["São Paulo", "Campinas", "Santos"], "MG": ["Belo Horizonte", "Uberlândia"],
    "RJ": ["Rio de Janeiro", "Niterói"], "BA": ["Salvador", "Feira de Santana"],
    "CE": ["Fortaleza", "Sobral", "Juazeiro do Norte"], "PR": ["Curitiba", "Londrina"],
    "PE": ["Recife", "Olinda", "Caruaru"], "RS": ["Porto Alegre", "Caxias do Sul"],
    "SC": ["Florianópolis", "Joinville"], "MA": ["São Luís", "Imperatriz"],
    "RN": ["Natal", "Mossoró"], "PB": ["João Pessoa", "Campina Grande"],
}
PORTES = ["MEI", "ME", "EPP", "Médio", "Grande"]
PORTE_P = [0.35, 0.40, 0.15, 0.08, 0.02]

STAGES = ["Novo", "Contato", "Reunião", "Proposta", "Ganho", "Perdido"]
FUNNEL = ["Novo", "Contato", "Reunião", "Proposta", "Ganho"] 
SELLERS = ["Ana", "Bruno", "Carla", "Diego", "Elisa"]

DEFAULT_ICP = {
    "id": "icp1", "name": "Software e TI no Nordeste", "version": 1,
    "cnaes": ["6201-5/00", "6204-0/00"], "ufs": ["CE", "PE", "BA", "RN"],
    "portes": ["ME", "EPP", "Médio"], "minAge": 2, "minCapital": 50000,
    "weights": {"cnae": 30, "uf": 20, "porte": 15, "idade": 10, "capital": 15, "contato": 10},
}
