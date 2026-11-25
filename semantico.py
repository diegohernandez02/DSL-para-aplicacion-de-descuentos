"""
Analizador semántico para el DSL de reglas de descuento.

Valida que una regla que ya pasó el análisis léxico y sintáctico tenga
sentido en el dominio de promociones y descuentos para e-commerce:
1. Atributos reconocidos por objeto (`CLIENTE`, `COMPRA`) y tipos esperados.
2. Compatibilidad de operadores relacionales (`=`, `==`, `!=`, `>`, `<`, `>=`, `<=`)
   con el tipo de dato del atributo y del operando (ej. no comparar `CLIENTE.nivel > 500`
   si `nivel` es categórico/texto, ni `COMPRA.total = "VIP"`).
3. Rango válido de porcentajes (`0%` a `100%`) tanto en `DESCUENTO(...)` como
   en comparaciones porcentuales.
4. Funciones de tiempo reconocidas (`TIEMPO(enrango)`, etc.) y coherencia de
   comparaciones numéricas (ej. `COMPRA.total >= 0`).
5. Detección básica de reglas/ramas redundantes o contradictorias dentro de un
   mismo bloque `SI ... SINO SI ... SINO ...`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class ErrorSemantico:
    codigo: str
    mensaje: str
    linea: int
    columna: int
    lexema: Optional[str] = None
    severidad: str = "ERROR"  # "ERROR" | "ADVERTENCIA"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "codigo": self.codigo,
            "severidad": self.severidad,
            "mensaje": self.mensaje,
            "linea": self.linea,
            "columna": self.columna,
            "lexema": self.lexema,
        }


class AnalizadorSemantico:
    """Valida coherencia de tipos, dominios, rangos y funciones en el árbol sintáctico."""

    # Esquema de atributos conocidos por objeto: atributo -> tipo ("TEXTO" | "NUMERO" | "PORCENTAJE")
    ATRIBUTOS_VALIDOS: Dict[str, Dict[str, str]] = {
        "CLIENTE": {
            "nivel": "TEXTO",
            "categoria": "TEXTO",
            "segmento": "TEXTO",
            "es_vip": "TEXTO",
            "antiguedad_meses": "NUMERO",
            "compras_realizadas": "NUMERO",
            "edad": "NUMERO",
        },
        "COMPRA": {
            "total": "NUMERO",
            "monto": "NUMERO",
            "subtotal": "NUMERO",
            "items": "NUMERO",
            "cantidad": "NUMERO",
            "descuento_actual": "PORCENTAJE",
        },
    }

    # Valores permitidos conocidos para atributos categóricos (si se evalúan con =, ==, !=)
    VALORES_CATEGORICOS: Dict[Tuple[str, str], Set[str]] = {
        ("CLIENTE", "nivel"): {"BRONCE", "PLATA", "ORO", "VIP", "REGULAR", "NUEVO"},
        ("CLIENTE", "categoria"): {"NUEVO", "RECURRENTE", "FRECUENTE", "VIP", "CORPORATIVO"},
        ("CLIENTE", "segmento"): {"RETAIL", "MAYORISTA", "VIP", "ESTUDIANTE"},
        ("CLIENTE", "es_vip"): {"SI", "NO", "TRUE", "FALSE", "VIP"},
    }

    # Funciones de tiempo reconocidas en TIEMPO(<id>)
    FUNCIONES_TIEMPO_VALIDAS: Set[str] = {
        "enrango",
        "en_rango",
        "vigente",
        "fin_de_semana",
        "horario_pico",
        "cyber",
        "black_friday",
        "temporada_alta",
    }

    OPERADORES_ORDEN: Set[str] = {">", "<", ">=", "<="}
    OPERADORES_IGUALDAD: Set[str] = {"=", "==", "!="}

    def __init__(
        self,
        atributos_validos: Optional[Dict[str, Dict[str, str]]] = None,
        funciones_tiempo: Optional[Set[str]] = None,
    ):
        self.atributos_validos = atributos_validos or self.ATRIBUTOS_VALIDOS
        self.funciones_tiempo = funciones_tiempo or self.FUNCIONES_TIEMPO_VALIDAS

    @staticmethod
    def _parsear_numero(lexema: str) -> Optional[float]:
        limpio = lexema.rstrip("%").strip()
        try:
            return float(limpio)
        except ValueError:
            return None

    def _inferir_tipo_operando(
        self,
        nodo_operando: Dict[str, Any],
        errores: List[ErrorSemantico],
    ) -> Tuple[Optional[str], Optional[float], Optional[str], Optional[int], Optional[int]]:
        """Devuelve (tipo_dato, valor_numerico, texto_limpio, linea, columna)."""
        hijos = nodo_operando.get("hijos", [])
        if not hijos:
            return None, None, None, None, None

        hoja = hijos[0]
        token_tipo = hoja.get("token")
        lexema = str(hoja.get("lexema", ""))
        linea = int(hoja.get("linea", 1))
        col = int(hoja.get("columna", 1))

        if token_tipo == "T_NUM":
            val = self._parsear_numero(lexema)
            return "NUMERO", val, lexema, linea, col

        if token_tipo == "T_PORCENTAJE":
            val = self._parsear_numero(lexema)
            if val is not None and (val < 0 or val > 100):
                errores.append(
                    ErrorSemantico(
                        codigo="SEM_RANGO_PORCENTAJE",
                        mensaje=f"El porcentaje '{lexema}' está fuera del rango permitido (0% a 100%).",
                        linea=linea,
                        columna=col,
                        lexema=lexema,
                    )
                )
            return "PORCENTAJE", val, lexema, linea, col

        if token_tipo == "T_CADENA":
            texto_sin_comillas = lexema[1:-1] if len(lexema) >= 2 else lexema
            return "TEXTO", None, texto_sin_comillas, linea, col

        if token_tipo == "T_ID":
            # En el DSL, un identificador sin comillas en COMPARACION suele ser un literal
            # simbólico (ej. VIP) o una variable/constante simbólica.
            return "TEXTO", None, lexema, linea, col

        return None, None, lexema, linea, col

    def _validar_accion(self, nodo_accion: Dict[str, Any], errores: List[ErrorSemantico]) -> Optional[float]:
        """Valida ACCION: T_APLICAR T_DESCUENTO T_PARI T_PORCENTAJE T_PARD."""
        hijos = nodo_accion.get("hijos", [])
        for h in hijos:
            if h.get("token") == "T_PORCENTAJE":
                lexema = str(h.get("lexema", ""))
                linea = int(h.get("linea", 1))
                col = int(h.get("columna", 1))
                valor = self._parsear_numero(lexema)
                if valor is None or valor < 1 or valor > 100:
                    errores.append(
                        ErrorSemantico(
                            codigo="SEM_DESCUENTO_FUERA_RANGO",
                            mensaje=f"El descuento '{lexema}' debe estar entre 1% y 100%.",
                            linea=linea,
                            columna=col,
                            lexema=lexema,
                        )
                    )
                elif valor == 0:
                    errores.append(
                        ErrorSemantico(
                            codigo="SEM_DESCUENTO_CERO",
                            severidad="ADVERTENCIA",
                            mensaje="La acción aplica un descuento de 0% (sin rebaja efectiva).",
                            linea=linea,
                            columna=col,
                            lexema=lexema,
                        )
                    )
                return valor
        return None

    def _validar_funcion_tiempo(self, nodo_func: Dict[str, Any], errores: List[ErrorSemantico]) -> None:
        """Valida FUNCION_TIEMPO: T_TIEMPO T_PARI T_ID T_PARD."""
        for h in nodo_func.get("hijos", []):
            if h.get("token") == "T_ID":
                param = str(h.get("lexema", ""))
                linea = int(h.get("linea", 1))
                col = int(h.get("columna", 1))
                if param not in self.funciones_tiempo:
                    errores.append(
                        ErrorSemantico(
                            codigo="SEM_FUNCION_TIEMPO_DESCONOCIDA",
                            mensaje=(
                                f"El parámetro '{param}' no es una condición de tiempo reconocida en TIEMPO(...). "
                                f"Válidos: {sorted(self.funciones_tiempo)}."
                            ),
                            linea=linea,
                            columna=col,
                            lexema=param,
                        )
                    )

    def _validar_comparacion(
        self,
        nodo_comp: Dict[str, Any],
        errores: List[ErrorSemantico],
        condiciones_vistas: List[Tuple[str, str, str]],
    ) -> None:
        """Valida COMPARACION: ATRIBUTO T_RELOP OPERANDO."""
        hijos = nodo_comp.get("hijos", [])
        if len(hijos) < 3:
            return

        nodo_attr, nodo_op, nodo_operando = hijos[0], hijos[1], hijos[2]
        attr_hijos = nodo_attr.get("hijos", [])
        if len(attr_hijos) < 3:
            return

        obj_node, _, id_node = attr_hijos[0], attr_hijos[1], attr_hijos[2]
        objeto = str(obj_node.get("lexema", ""))
        campo = str(id_node.get("lexema", ""))
        linea_campo = int(id_node.get("linea", 1))
        col_campo = int(id_node.get("columna", 1))

        operador = str(nodo_op.get("lexema", ""))
        linea_op = int(nodo_op.get("linea", linea_campo))
        col_op = int(nodo_op.get("columna", col_campo))

        # 1. Verificar que el objeto y atributo existan en el esquema
        campos_obj = self.atributos_validos.get(objeto)
        if campos_obj is None:
            errores.append(
                ErrorSemantico(
                    codigo="SEM_OBJETO_DESCONOCIDO",
                    mensaje=f"Objeto '{objeto}' no reconocido.",
                    linea=int(obj_node.get("linea", 1)),
                    columna=int(obj_node.get("columna", 1)),
                    lexema=objeto,
                )
            )
            return

        if campo not in campos_obj:
            errores.append(
                ErrorSemantico(
                    codigo="SEM_ATRIBUTO_DESCONOCIDO",
                    mensaje=(
                        f"El atributo '{campo}' no existe para '{objeto}'. "
                        f"Disponibles: {sorted(campos_obj.keys())}."
                    ),
                    linea=linea_campo,
                    columna=col_campo,
                    lexema=campo,
                )
            )
            return

        tipo_campo = campos_obj[campo]

        # 2. Evaluar operando
        tipo_operando, valor_num, texto_val, linea_val, col_val = self._inferir_tipo_operando(
            nodo_operando, errores
        )

        # 3. Compatibilidad de operador y tipo
        if operador in self.OPERADORES_ORDEN:
            if tipo_campo not in ("NUMERO", "PORCENTAJE") or tipo_operando not in ("NUMERO", "PORCENTAJE"):
                errores.append(
                    ErrorSemantico(
                        codigo="SEM_OPERADOR_INCOMPATIBLE",
                        mensaje=(
                            f"El operador '{operador}' requiere valores numéricos/porcentuales; "
                            f"se encontró '{objeto}.{campo}' ({tipo_campo}) con '{texto_val}' ({tipo_operando})."
                        ),
                        linea=linea_op,
                        columna=col_op,
                        lexema=operador,
                    )
                )
            elif valor_num is not None and valor_num < 0:
                errores.append(
                    ErrorSemantico(
                        codigo="SEM_VALOR_NEGATIVO_NO_PERMITIDO",
                        mensaje=f"El valor '{texto_val}' no puede ser negativo para '{objeto}.{campo}'.",
                        linea=linea_val or linea_op,
                        columna=col_val or col_op,
                        lexema=texto_val,
                    )
                )
        elif operador in self.OPERADORES_IGUALDAD:
            if tipo_campo == "TEXTO" and tipo_operando not in ("TEXTO",):
                errores.append(
                    ErrorSemantico(
                        codigo="SEM_TIPO_INCOMPATIBLE",
                        mensaje=(
                            f"No se puede comparar '{objeto}.{campo}' (TEXTO) con '{texto_val}' ({tipo_operando})."
                        ),
                        linea=linea_op,
                        columna=col_op,
                        lexema=operador,
                    )
                )
            elif tipo_campo in ("NUMERO", "PORCENTAJE") and tipo_operando not in ("NUMERO", "PORCENTAJE"):
                errores.append(
                    ErrorSemantico(
                        codigo="SEM_TIPO_INCOMPATIBLE",
                        mensaje=(
                            f"No se puede comparar '{objeto}.{campo}' ({tipo_campo}) con '{texto_val}' ({tipo_operando})."
                        ),
                        linea=linea_op,
                        columna=col_op,
                        lexema=operador,
                    )
                )

            # Validar valor categórico conocido si aplica
            clave_cat = (objeto, campo)
            if tipo_campo == "TEXTO" and clave_cat in self.VALORES_CATEGORICOS and texto_val is not None:
                permitidos = self.VALORES_CATEGORICOS[clave_cat]
                if texto_val.upper() not in permitidos:
                    errores.append(
                        ErrorSemantico(
                            codigo="SEM_VALOR_CATEGORIA_INVALIDO",
                            severidad="ADVERTENCIA",
                            mensaje=(
                                f"El valor '{texto_val}' no está en el catálogo habitual de {objeto}.{campo} "
                                f"({sorted(permitidos)})."
                            ),
                            linea=linea_val or linea_campo,
                            columna=col_val or col_campo,
                            lexema=texto_val,
                        )
                    )

        # 4. Detectar condición duplicada dentro de la misma cadena condicional
        firma = (f"{objeto}.{campo}", operador, str(texto_val))
        if firma in condiciones_vistas:
            errores.append(
                ErrorSemantico(
                    codigo="SEM_CONDICION_DUPLICADA",
                    severidad="ADVERTENCIA",
                    mensaje=f"La condición '{firma[0]} {firma[1]} {firma[2]}' ya aparece evaluada previamente.",
                    linea=linea_campo,
                    columna=col_campo,
                    lexema=f"{firma[0]} {firma[1]} {firma[2]}",
                )
            )
        else:
            condiciones_vistas.append(firma)

    def _recorrer_nodo(
        self,
        nodo: Optional[Dict[str, Any]],
        errores: List[ErrorSemantico],
        condiciones_vistas: List[Tuple[str, str, str]],
        descuentos_rama: List[float],
    ) -> None:
        if not isinstance(nodo, dict):
            return

        simbolo = nodo.get("nodo")
        if simbolo == "COMPARACION":
            self._validar_comparacion(nodo, errores, condiciones_vistas)
            return
        if simbolo == "FUNCION_TIEMPO":
            self._validar_funcion_tiempo(nodo, errores)
            return
        if simbolo == "ACCION":
            val_desc = self._validar_accion(nodo, errores)
            if val_desc is not None:
                descuentos_rama.append(val_desc)
            return

        # Si inicia una nueva REGLA independiente, reiniciamos el historial de condiciones de esa regla
        if simbolo == "REGLA":
            condiciones_vistas = []
            descuentos_rama = []

        for hijo in nodo.get("hijos", []):
            self._recorrer_nodo(hijo, errores, condiciones_vistas, descuentos_rama)

        if simbolo == "REGLA" and len(descuentos_rama) >= 2:
            if len(set(descuentos_rama)) == 1:
                errores.append(
                    ErrorSemantico(
                        codigo="SEM_DESCUENTO_REDUNDANTE",
                        severidad="ADVERTENCIA",
                        mensaje=(
                            f"Todas las ramas de la regla aplican el mismo descuento ({descuentos_rama[0]}%), "
                            "lo que hace redundante la bifurcación."
                        ),
                        linea=1,
                        columna=1,
                        lexema="REGLA",
                    )
                )

    def analizar_arbol(self, arbol: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Analiza el árbol sintáctico (en formato dict) y devuelve errores/advertencias semánticas."""
        errores: List[ErrorSemantico] = []
        if not arbol:
            return {
                "valido_semantico": False,
                "errores_semanticos": [],
                "advertencias_semanticas": [],
                "tiene_errores": False,
            }

        self._recorrer_nodo(arbol, errores, [], [])

        solo_errores = [e.to_dict() for e in errores if e.severidad == "ERROR"]
        advertencias = [e.to_dict() for e in errores if e.severidad == "ADVERTENCIA"]

        return {
            "valido_semantico": len(solo_errores) == 0,
            "errores_semanticos": solo_errores,
            "advertencias_semanticas": advertencias,
            "tiene_errores": len(solo_errores) > 0,
        }


if __name__ == "__main__":
    from lexer import tokenizar
    from parser_meta import MetacompiladorSintactico

    parser_meta = MetacompiladorSintactico()
    sem = AnalizadorSemantico()

    casos = [
        # 1. Válida semánticamente
        "SI CLIENTE.nivel = VIP Y COMPRA.total > 500 Y TIEMPO(enrango) ENTONCES APLICAR DESCUENTO(15%)",
        # 2. Error semántico: atributo inexistente + descuento > 100% + operador '>' en texto
        "SI CLIENTE.nivel > 500 Y COMPRA.monto_inexistente >= 100 ENTONCES APLICAR DESCUENTO(150%)",
        # 3. Error semántico: parámetro de tiempo no reconocido
        "SI TIEMPO(feriado_inventado) ENTONCES APLICAR DESCUENTO(10%)",
    ]

    for i, regla in enumerate(casos, 1):
        lex = tokenizar(regla)
        sint = parser_meta.analizar_tokens(lex["tokens"])
        print(f"=== Caso {i}: {regla} ===")
        if not sint["valido"]:
            print("Falló en sintaxis:", sint["errores_sintacticos"])
            continue
        res_sem = sem.analizar_arbol(sint["arbol"])
        print("Válido semánticamente:", res_sem["valido_semantico"])
        print("Errores:", res_sem["errores_semanticos"])
        print("Advertencias:", res_sem["advertencias_semanticas"])
        print()
