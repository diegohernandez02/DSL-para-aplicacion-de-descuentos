"""
Generador de objeto JSON estructurado para el DSL de reglas de descuento.

Transforma el árbol sintáctico validado (léxica, sintáctica y semánticamente)
en una representación JSON limpia, lista para ser exportada o consumida por
sistemas externos (fuera del alcance de ejecución de este proyecto).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class GeneradorJSONReglas:
    """Convierte el árbol sintáctico validado en un objeto JSON estructurado."""

    @staticmethod
    def _extraer_factor(nodo_factor: Dict[str, Any]) -> Dict[str, Any]:
        hijos = nodo_factor.get("hijos", [])
        if not hijos:
            return {}

        primero = hijos[0]
        if primero.get("token") == "T_NOT":
            return {
                "tipo": "NEGACION",
                "operando": GeneradorJSONReglas._extraer_factor(hijos[1]),
            }
        if primero.get("token") == "T_PARI":
            return {
                "tipo": "GRUPO",
                "expresion": GeneradorJSONReglas._extraer_condicion(hijos[1]),
            }
        if primero.get("nodo") == "COMPARACION":
            comp_hijos = primero.get("hijos", [])
            attr_hijos = comp_hijos[0].get("hijos", [])
            op_node = comp_hijos[1]
            val_node = comp_hijos[2].get("hijos", [])[0]

            objeto = attr_hijos[0].get("lexema")
            atributo = attr_hijos[2].get("lexema")
            operador = op_node.get("lexema")
            val_token = val_node.get("token")
            val_lexema = str(val_node.get("lexema", ""))

            valor_parseado: Any = val_lexema
            if val_token == "T_NUM":
                valor_parseado = float(val_lexema) if "." in val_lexema else int(val_lexema)
            elif val_token == "T_PORCENTAJE":
                num_str = val_lexema.rstrip("%")
                valor_parseado = float(num_str) if "." in num_str else int(num_str)
            elif val_token == "T_CADENA" and len(val_lexema) >= 2:
                valor_parseado = val_lexema[1:-1]

            return {
                "tipo": "COMPARACION",
                "objeto": objeto,
                "atributo": atributo,
                "operador": operador,
                "valor": valor_parseado,
                "tipo_valor": val_token,
            }

        if primero.get("nodo") == "FUNCION_TIEMPO":
            func_hijos = primero.get("hijos", [])
            parametro = func_hijos[2].get("lexema") if len(func_hijos) >= 3 else ""
            return {
                "tipo": "FUNCION_TIEMPO",
                "funcion": "TIEMPO",
                "parametro": parametro,
            }

        return {}

    @staticmethod
    def _extraer_termino(nodo_termino: Dict[str, Any]) -> Dict[str, Any]:
        hijos = nodo_termino.get("hijos", [])
        izquierda = GeneradorJSONReglas._extraer_factor(hijos[0])
        tail = hijos[1] if len(hijos) > 1 else {}
        tail_hijos = tail.get("hijos", [])

        if not tail_hijos:
            return izquierda

        operadores = [izquierda]
        actual_tail = tail
        while actual_tail.get("hijos"):
            th = actual_tail["hijos"]
            operadores.append(GeneradorJSONReglas._extraer_factor(th[1]))
            actual_tail = th[2]

        return {"operador_logico": "AND", "operandos": operadores}

    @staticmethod
    def _extraer_condicion(nodo_condicion: Dict[str, Any]) -> Dict[str, Any]:
        hijos = nodo_condicion.get("hijos", [])
        izquierda = GeneradorJSONReglas._extraer_termino(hijos[0])
        tail = hijos[1] if len(hijos) > 1 else {}
        tail_hijos = tail.get("hijos", [])

        if not tail_hijos:
            return izquierda

        operadores = [izquierda]
        actual_tail = tail
        while actual_tail.get("hijos"):
            th = actual_tail["hijos"]
            operadores.append(GeneradorJSONReglas._extraer_termino(th[1]))
            actual_tail = th[2]

        return {"operador_logico": "OR", "operandos": operadores}

    @staticmethod
    def _extraer_accion(nodo_accion: Dict[str, Any]) -> Dict[str, Any]:
        hijos = nodo_accion.get("hijos", [])
        porcentaje_str = "0%"
        for h in hijos:
            if h.get("token") == "T_PORCENTAJE":
                porcentaje_str = str(h.get("lexema", "0%"))
                break
        num_str = porcentaje_str.rstrip("%")
        porcentaje_num = float(num_str) if "." in num_str else int(num_str)
        return {
            "tipo": "APLICAR_DESCUENTO",
            "porcentaje": porcentaje_num,
            "etiqueta": porcentaje_str,
        }

    @classmethod
    def _extraer_regla(cls, nodo_regla: Dict[str, Any], indice: int) -> Dict[str, Any]:
        hijos = nodo_regla.get("hijos", [])
        ramas: List[Dict[str, Any]] = [
            {
                "tipo_rama": "SI",
                "condicion": cls._extraer_condicion(hijos[1]),
                "accion": cls._extraer_accion(hijos[3]),
            }
        ]

        resto = hijos[4] if len(hijos) > 4 else {}
        while resto.get("hijos"):
            rh = resto["hijos"]
            if len(rh) >= 6 and rh[1].get("token") == "T_SI":
                ramas.append(
                    {
                        "tipo_rama": "SINO_SI",
                        "condicion": cls._extraer_condicion(rh[2]),
                        "accion": cls._extraer_accion(rh[4]),
                    }
                )
                resto = rh[5]
            elif len(rh) == 2 and rh[0].get("token") == "T_SINO":
                ramas.append(
                    {
                        "tipo_rama": "SINO",
                        "condicion": None,
                        "accion": cls._extraer_accion(rh[1]),
                    }
                )
                break
            else:
                break

        return {
            "id_regla": f"REG-{indice:03d}",
            "ramas": ramas,
        }

    @classmethod
    def generar(cls, arbol: Optional[Dict[str, Any]], fuente_dsl: str = "") -> Dict[str, Any]:
        if not arbol:
            return {}

        reglas: List[Dict[str, Any]] = []

        def recolectar(nodo: Dict[str, Any]) -> None:
            if nodo.get("nodo") == "REGLA":
                reglas.append(cls._extraer_regla(nodo, len(reglas) + 1))
                return
            for hijo in nodo.get("hijos", []):
                if isinstance(hijo, dict):
                    recolectar(hijo)

        recolectar(arbol)

        objeto_json = {
            "esquema": "dsl-descuentos-ecommerce/v1",
            "estado": "VALIDADO",
            "generado_en": datetime.now(timezone.utc).isoformat(),
            "total_reglas": len(reglas),
            "reglas": reglas,
        }
        return {
            "objeto": objeto_json,
            "json_texto": json.dumps(objeto_json, indent=2, ensure_ascii=False),
        }