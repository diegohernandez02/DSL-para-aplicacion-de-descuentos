"""
Definición formal de AFND, AFD y tablas de transiciones para los tokens
T_ID, T_NUM, T_PORCENTAJE y T_RELOP del DSL de descuentos,
asociando los lexemas reconocidos en la entrada analizada.
"""

from __future__ import annotations

from typing import Any, Dict, List


_BASE_AUTOMATAS: List[Dict[str, Any]] = [
    {
        "token": "T_ID",
        "expresion_regular": r"[A-Za-z_][A-Za-z0-9_]*",
        "descripcion": "Identificador que inicia con letra o '_' seguido de letras, dígitos o '_'.",
        "afnd": {
            "estados": ["q0", "q1", "q2", "q3"],
            "inicial": "q0",
            "aceptacion": ["q3"],
            "alfabeto": ["letra / '_'", "dígito", "'_'", "ε"],
            "transiciones": [
                {"origen": "q0", "simbolo": "letra / '_'", "destinos": ["q1"]},
                {"origen": "q1", "simbolo": "ε", "destinos": ["q2"]},
                {"origen": "q2", "simbolo": "letra / '_'", "destinos": ["q2", "q3"]},
                {"origen": "q2", "simbolo": "dígito", "destinos": ["q2", "q3"]},
                {"origen": "q3", "simbolo": "ε", "destinos": ["q2"]},
            ],
        },
        "afd": {
            "estados": ["S0", "S1"],
            "inicial": "S0",
            "aceptacion": ["S1"],
            "alfabeto": ["letra / '_'", "dígito"],
            "tabla": [
                {"estado": "→ S0", "letra / '_'": "S1", "dígito": "—"},
                {"estado": "* S1", "letra / '_'": "S1", "dígito": "S1"},
            ],
            "columnas": ["estado", "letra / '_'", "dígito"],
        },
    },
    {
        "token": "T_NUM",
        "expresion_regular": r"[0-9]+(\.[0-9]+)?",
        "descripcion": "Número entero o decimal positivo sin signo de porcentaje.",
        "afnd": {
            "estados": ["q0", "q1", "q2", "q3", "q4"],
            "inicial": "q0",
            "aceptacion": ["q1", "q4"],
            "alfabeto": ["dígito [0-9]", "'.'", "ε"],
            "transiciones": [
                {"origen": "q0", "simbolo": "dígito [0-9]", "destinos": ["q1"]},
                {"origen": "q1", "simbolo": "dígito [0-9]", "destinos": ["q1"]},
                {"origen": "q1", "simbolo": "ε", "destinos": ["q2"]},
                {"origen": "q2", "simbolo": "'.'", "destinos": ["q3"]},
                {"origen": "q3", "simbolo": "dígito [0-9]", "destinos": ["q4"]},
                {"origen": "q4", "simbolo": "dígito [0-9]", "destinos": ["q4"]},
            ],
        },
        "afd": {
            "estados": ["S0", "S1", "S2", "S3"],
            "inicial": "S0",
            "aceptacion": ["S1", "S3"],
            "alfabeto": ["dígito [0-9]", "'.'"],
            "tabla": [
                {"estado": "→ S0", "dígito [0-9]": "S1", "'.'": "—"},
                {"estado": "* S1", "dígito [0-9]": "S1", "'.'": "S2"},
                {"estado": "S2", "dígito [0-9]": "S3", "'.'": "—"},
                {"estado": "* S3", "dígito [0-9]": "S3", "'.'": "—"},
            ],
            "columnas": ["estado", "dígito [0-9]", "'.'"],
        },
    },
    {
        "token": "T_PORCENTAJE",
        "expresion_regular": r"[0-9]+(\.[0-9]+)?%",
        "descripcion": "Valor numérico entero o decimal terminado obligatoriamente en '%'.",
        "afnd": {
            "estados": ["q0", "q1", "q2", "q3", "q4", "q5"],
            "inicial": "q0",
            "aceptacion": ["q5"],
            "alfabeto": ["dígito [0-9]", "'.'", "'%'", "ε"],
            "transiciones": [
                {"origen": "q0", "simbolo": "dígito [0-9]", "destinos": ["q1"]},
                {"origen": "q1", "simbolo": "dígito [0-9]", "destinos": ["q1"]},
                {"origen": "q1", "simbolo": "ε", "destinos": ["q2", "q4"]},
                {"origen": "q2", "simbolo": "'.'", "destinos": ["q3"]},
                {"origen": "q3", "simbolo": "dígito [0-9]", "destinos": ["q3", "q4"]},
                {"origen": "q4", "simbolo": "'%'", "destinos": ["q5"]},
            ],
        },
        "afd": {
            "estados": ["S0", "S1", "S2", "S3", "S4"],
            "inicial": "S0",
            "aceptacion": ["S4"],
            "alfabeto": ["dígito [0-9]", "'.'", "'%'"],
            "tabla": [
                {"estado": "→ S0", "dígito [0-9]": "S1", "'.'": "—", "'%'": "—"},
                {"estado": "S1", "dígito [0-9]": "S1", "'.'": "S2", "'%'": "S4"},
                {"estado": "S2", "dígito [0-9]": "S3", "'.'": "—", "'%'": "—"},
                {"estado": "S3", "dígito [0-9]": "S3", "'.'": "—", "'%'": "S4"},
                {"estado": "* S4", "dígito [0-9]": "—", "'.'": "—", "'%'": "—"},
            ],
            "columnas": ["estado", "dígito [0-9]", "'.'", "'%'"],
        },
    },
    {
        "token": "T_RELOP",
        "expresion_regular": r"==|!=|>=|<=|=|>|<",
        "descripcion": "Operadores relacionales de igualdad, desigualdad y orden.",
        "afnd": {
            "estados": ["q0", "q1", "q1a", "q2", "q3", "q3a", "q4", "q5", "q5a", "q6", "q7", "q7a", "q8", "q9", "q10"],
            "inicial": "q0",
            "aceptacion": ["q2", "q4", "q6", "q8", "q9", "q10"],
            "alfabeto": ["'='", "'!'", "'>'", "'<'", "ε"],
            "transiciones": [
                {"origen": "q0", "simbolo": "ε", "destinos": ["q1", "q3", "q5", "q7", "q9", "q10"]},
                {"origen": "q1", "simbolo": "'='", "destinos": ["q1a"]},
                {"origen": "q1a", "simbolo": "'='", "destinos": ["q2"]},
                {"origen": "q3", "simbolo": "'!'", "destinos": ["q3a"]},
                {"origen": "q3a", "simbolo": "'='", "destinos": ["q4"]},
                {"origen": "q5", "simbolo": "'>'", "destinos": ["q5a"]},
                {"origen": "q5a", "simbolo": "'='", "destinos": ["q6"]},
                {"origen": "q7", "simbolo": "'<'", "destinos": ["q7a"]},
                {"origen": "q7a", "simbolo": "'='", "destinos": ["q8"]},
                {"origen": "q9", "simbolo": "'='", "destinos": ["q9"]},
                {"origen": "q10", "simbolo": "'>' / '<'", "destinos": ["q10"]},
            ],
        },
        "afd": {
            "estados": ["S0", "S1", "S2", "S3", "S4", "S5", "S6"],
            "inicial": "S0",
            "aceptacion": ["S1", "S2", "S3", "S4", "S5", "S6"],
            "alfabeto": ["'='", "'!'", "'>'", "'<'"],
            "tabla": [
                {"estado": "→ * S0", "'='": "S1", "'!'": "S2", "'>'": "S3", "'<'": "S4"},
                {"estado": "* S1", "'='": "S5", "'!'": "—", "'>'": "—", "'<'": "—"},
                {"estado": "S2", "'='": "S6", "'!'": "—", "'>'": "—", "'<'": "—"},
                {"estado": "* S3", "'='": "S6", "'!'": "—", "'>'": "—", "'<'": "—"},
                {"estado": "* S4", "'='": "S6", "'!'": "—", "'>'": "—", "'<'": "—"},
                {"estado": "* S5", "'='": "—", "'!'": "—", "'>'": "—", "'<'": "—"},
                {"estado": "* S6", "'='": "—", "'!'": "—", "'>'": "—", "'<'": "—"},
            ],
            "columnas": ["estado", "'='", "'!'", "'>'", "'<'"],
        },
    },
]


def obtener_automatas_tokens(tokens: List[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
    """Devuelve los autómatas AFND, AFD y tablas de transiciones con los lexemas reconocidos en la entrada."""
    por_token: Dict[str, List[str]] = {
        "T_ID": [],
        "T_NUM": [],
        "T_PORCENTAJE": [],
        "T_RELOP": [],
    }
    vistos: Dict[str, set[str]] = {k: set() for k in por_token}

    for tok in tokens or []:
        tipo = tok.get("token")
        lexema = str(tok.get("lexema", ""))
        if tipo in por_token and lexema and lexema not in vistos[tipo]:
            vistos[tipo].add(lexema)
            por_token[tipo].append(lexema)

    resultado: List[Dict[str, Any]] = []
    for item in _BASE_AUTOMATAS:
        copia = dict(item)
        copia["lexemas_reconocidos"] = por_token[item["token"]]
        resultado.append(copia)
    return resultado
