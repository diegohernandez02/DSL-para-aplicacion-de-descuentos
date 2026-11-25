grammar Descuentos;

// ============================================================================
// GRAMÁTICA LIBRE DE CONTEXTO (GLC) - DSL DE REGLAS DE DESCUENTO
// ============================================================================

programa
    : regla+ EOF
    ;

regla
    : T_SI condicion T_ENTONCES accion resto
    ;

resto
    : T_SINO T_SI condicion T_ENTONCES accion resto   # RestoSinoSi
    | T_SINO accion                                   # RestoSinoFinal
    |                                                 # RestoVacio
    ;

condicion
    : condicion T_OR termino                          # CondicionOr
    | termino                                         # CondicionTermino
    ;

termino
    : termino T_AND factor                            # TerminoAnd
    | factor                                          # TerminoFactor
    ;

factor
    : T_NOT factor                                    # FactorNot
    | T_PARI condicion T_PARD                         # FactorAgrupado
    | comparacion                                     # FactorComparacion
    | funcionTiempo                                   # FactorFuncionTiempo
    ;

comparacion
    : atributo T_RELOP operando
    ;

atributo
    : T_OBJETO T_PUNTO T_ID
    ;

funcionTiempo
    : T_TIEMPO T_PARI T_ID T_PARD
    ;

operando
    : T_ID                                            # OperandoId
    | T_NUM                                           # OperandoNum
    | T_PORCENTAJE                                    # OperandoPorcentaje
    | T_CADENA                                        # OperandoCadena
    ;

accion
    : T_APLICAR T_DESCUENTO T_PARI T_PORCENTAJE T_PARD
    ;

// ============================================================================
// ESPECIFICACIÓN LÉXICA (TOKENS)
// ============================================================================

T_SI        : 'SI' ;
T_SINO      : 'SINO' ;
T_ENTONCES  : 'ENTONCES' ;
T_APLICAR   : 'APLICAR' ;
T_DESCUENTO : 'DESCUENTO' ;
T_AND       : 'Y' ;
T_OR        : 'O' ;
T_NOT       : 'NO' ;
T_OBJETO    : 'CLIENTE' | 'COMPRA' ;
T_TIEMPO    : 'TIEMPO' ;

T_RELOP     : '==' | '!=' | '>=' | '<=' | '=' | '>' | '<' ;

T_PUNTO     : '.' ;
T_PARI      : '(' ;
T_PARD      : ')' ;

T_PORCENTAJE: [0-9]+ ('.' [0-9]+)? '%' ;
T_NUM       : [0-9]+ ('.' [0-9]+)? ;
T_CADENA    : '"' (~["\r\n])* '"' | '\'' (~['\r\n])* '\'' ;
T_ID        : [a-zA-Z_] [a-zA-Z0-9_]* ;

WS          : [ \t\r\n]+ -> skip ;
COMMENT     : '//' ~[\r\n]* -> skip ;
