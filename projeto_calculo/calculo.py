import re
import unicodedata
import sympy as sp
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sympy.integrals.manualintegrate import manualintegrate, integral_steps

app = FastAPI()

@app.get("/")
def home():
    return FileResponse("index.html")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def tratar_expressao(expr: str) -> str:
    """Trata a entrada do usuário para aceitar sintaxe matemática humana, incluindo equivalências e proteções."""
    if not expr:
        return expr

    # 1. Converter tudo para minúsculo
    expr = expr.lower()

    # 2. Dicionário Unificado de Equivalências (Aliases) - PT/EN e variações comuns
    equivalencias = {
        # Trigonométricas Diretas
        'sen': 'sin', 'tg': 'tan', 'ctg': 'cot', 'cotan': 'cot', 'cosec': 'csc',
        # Trigonométricas Inversas
        'arcsen': 'asin', 'arcsin': 'asin', 'sen^-1': 'asin', 'sin^-1': 'asin',
        'arccos': 'acos', 'cos^-1': 'acos',
        'arctg': 'atan', 'arctan': 'atan', 'tan^-1': 'atan', 'tg^-1': 'atan',
        'arcsec': 'asec', 'sec^-1': 'asec',
        'arccsc': 'acsc', 'csc^-1': 'acsc',
        'arccot': 'acot', 'cot^-1': 'acot', 'ctg^-1': 'acot',
        # Hiperbólicas Diretas e Inversas
        'senh': 'sinh', 'tgh': 'tanh',
        'arcsinh': 'asinh', 'asenh': 'asinh',
        'arccosh': 'acosh',
        'arctanh': 'atanh', 'atgh': 'atanh'
    }
    
    # Ordenar as chaves por tamanho decrescente para evitar conflito (ex: 'sen' vs 'senh')
    for termo in sorted(equivalencias.keys(), key=len, reverse=True):
        original = equivalencias[termo]
        expr = expr.replace(termo, original)

    # 3. Converte caracteres Unicode sobrescritos (ex: ², ³, etc.)
    padrao_sobrescritos = r'([\u00B2\u00B3\u00B9\u2070-\u209C]+)'
    def reemp_sobrescrito(match):
        texto = unicodedata.normalize('NFKC', match.group(1))
        return f"^({texto})"
    expr = re.sub(padrao_sobrescritos, reemp_sobrescrito, expr)

    # 4. Transforma '^' em '**'
    expr = expr.replace('^', '**')

    # Lista completa de funções mapeadas para processamento
    funcoes = [
        'sinh', 'cosh', 'tanh', 'sech', 'csch', 'coth',
        'asinh', 'acosh', 'atanh',
        'sin', 'cos', 'tan', 'sec', 'csc', 'cot',
        'asin', 'acos', 'atan', 'asec', 'acsc', 'acot',
        'log', 'ln', 'exp', 'sqrt'
    ]

    # Proteção: Se digitar apenas o nome da função sem parenteses, adiciona (x)
    for func in funcoes:
        if expr.strip() == func:
            expr = f"{func}(x)"

    # Insere '*' entre número/variável e funções (ex: 2sin -> 2*sin)
    for func in funcoes:
        expr = re.sub(rf'([0-9a-zA-Z\)])\s*{func}', rf'\1*{func}', expr)

    # 5. Substitui ponto de multiplicação por '*'
    expr = re.sub(r'(\d)\.(?=[a-zA-Z\(])', r'\1*', expr)
    expr = re.sub(r'([a-zA-Z\)])\.(?=[a-zA-Z0-9\(])', r'\1*', expr)

    # 6. Multiplicação implícita genérica
    expr = re.sub(r'(\d)\s*([xX\(])', r'\1*\2', expr)
    expr = re.sub(r'(\))\s*([\dxX\(])', r'\1*\2', expr)

    return expr

def para_float_seguro(val):
    """Converte valores do SymPy para float com segurança."""
    try:
        res = complex(sp.N(val))
        if abs(res.imag) < 1e-9:
            return round(res.real, 4)
        return "⚠️ Resultado Complexo/Não Real"
    except Exception:
        return None

def gerar_passos_derivada(f, x):
    """Gera uma explicação didática dos passos da derivada usando o banco de deduções tabeladas."""
    passos = []
    
    # BANCO DE DEDUÇÕES TABELADAS (Para funções puras em x)
    deducoes_tabela = {
        sp.sin(x): [
            "• **Derivada Fundamental**: A derivada do $\\sin(x)$ é calculada pelo limite do quociente de Newton, resultando diretamente em $\\cos(x)$."
        ],
        sp.cos(x): [
            "• **Derivada Fundamental**: A derivada do $\\cos(x)$ resulta no valor negativo do seno, ou seja, $-\\sin(x)$."
        ],
        sp.tan(x): [
            "• **Dedução via Regra do Quociente**: Reescrevemos $\\tan(x) = \\frac{\\sin(x)}{\\cos(x)}$.",
            "• Aplicando $\\left(\\frac{u}{v}\\right)' = \\frac{u'v - uv'}{v^2}$, temos: $\\frac{\\cos(x)\\cos(x) - \\sin(x)(-\\sin(x))}{\\cos^2(x)}$",
            "• Usando a Identidade Fundamental $\\sin^2(x) + \\cos^2(x) = 1$, obtemos $\\frac{1}{\\cos^2(x)} = \\sec^2(x)$."
        ],
        sp.sec(x): [
            "• **Dedução**: Reescrevemos $\\sec(x) = (\\cos(x))^{-1}$.",
            "• Aplicando a regra da potência e da cadeia: $-1(\\cos(x))^{-2} \\cdot (-\\sin(x)) = \\frac{\\sin(x)}{\\cos^2(x)}$",
            "• Separando as frações, obtemos: $\\frac{1}{\\cos(x)} \\cdot \\frac{\\sin(x)}{\\cos(x)} = \\sec(x)\\tan(x)$."
        ],
        sp.cot(x): [
            "• **Dedução via Regra do Quociente**: Reescrevemos $\\cot(x) = \\frac{\\cos(x)}{\\sin(x)}$.",
            "• Aplicando a regra do quociente, o numerador torna-se $-\\sin^2(x) - \\cos^2(x) = -1$.",
            "• O resultado final consolidado é $-\\frac{1}{\\sin^2(x)} = -\\csc^2(x)$."
        ],
        sp.csc(x): [
            "• **Dedução**: Reescrevemos $\\csc(x) = (\\sin(x))^{-1}$.",
            "• Derivando via regra da cadeia: $-1(\\sin(x))^{-2} \\cdot \\cos(x) = -\\frac{\\cos(x)}{\\sin^2(x)}$.",
            "• Simplificando a expressão trigonométrica, chegamos a $-\\csc(x)\\cot(x)$."
        ],
        sp.asin(x): [
            "• **Dedução via Derivação Implícita**: Seja $y = \\arcsin(x) \\implies \\sin(y) = x$.",
            "• Derivando implicitamente em relação a $x$: $\\cos(y) \\cdot y' = 1 \\implies y' = \\frac{1}{\\cos(y)}$.",
            "• Usando a relação $\\cos(y) = \\sqrt{1 - \\sin^2(y)}$ e substituindo $\\sin(y) = x$, chegamos a $\\frac{1}{\\sqrt{1 - x^2}}$."
        ],
        sp.acos(x): [
            "• **Dedução via Derivação Implícita**: Seja $y = \\arccos(x) \\implies \\cos(y) = x$.",
            "• Derivando implicitamente em relação a $x$: $-\\sin(y) \\cdot y' = 1 \\implies y' = -\\frac{1}{\\sin(y)}$.",
            "• Substituindo pela identidade trigonométrica fundamental, obtemos $-\\frac{1}{\\sqrt{1 - x^2}}$."
        ],
        sp.atan(x): [
            "• **Dedução via Derivação Implícita**: Seja $y = \\arctan(x) \\implies \\tan(y) = x$.",
            "• Derivando implicitamente em relação a $x$: $\\sec^2(y) \\cdot y' = 1 \\implies y' = \\frac{1}{\\sec^2(y)}$.",
            "• Utilizando a identidade geométrica $\\sec^2(y) = 1 + \\tan^2(y)$ e trocando por $x$, temos $\\frac{1}{1 + x^2}$."
        ],
        sp.asec(x): [
            "• **Dedução via Derivação Implícita**: Seja $y = \\arcsec(x) \\implies \\sec(y) = x$.",
            "• Derivando implicitamente: $\\sec(y)\\tan(y) \\cdot y' = 1 \\implies y' = \\frac{1}{\\sec(y)\\tan(y)}$.",
            "• Como $\\tan(y) = \\sqrt{\\sec^2(y) - 1}$ e $\\sec(y) = x$, obtemos $\\frac{1}{|x|\\sqrt{x^2 - 1}}$."
        ],
        sp.acsc(x): [
            "• **Dedução via Derivação Implícita**: Seja $y = \\arccsc(x) \\implies \\csc(y) = x$.",
            "• Derivando implicitamente: $-\\csc(y)\\cot(y) \\cdot y' = 1 \\implies y' = -\\frac{1}{\\csc(y)\\cot(y)}$.",
            "• Substituindo as identidades correspondentes, resulta em $-\\frac{1}{|x|\\sqrt{x^2 - 1}}$."
        ],
        sp.acot(x): [
            "• **Dedução via Derivação Implícita**: Seja $y = \\arccot(x) \\implies \\cot(y) = x$.",
            "• Derivando implicitamente: $-\\csc^2(y) \\cdot y' = 1 \\implies y' = -\\frac{1}{\\csc^2(y)}$.",
            "• Como $\\csc^2(y) = 1 + \\cot^2(y)$, substituímos para obter $-\\frac{1}{1 + x^2}$."
        ],
        sp.asinh(x): [
            "• **Dedução via Derivação Implícita**: Seja $y = \\text{arcsinh}(x) \\implies \\sinh(y) = x$.",
            "• Derivando implicitamente: $\\cosh(y) \\cdot y' = 1 \\implies y' = \\frac{1}{\\cosh(y)}$.",
            "• Usando a relação fundamental hiperbólica $\\cosh(y) = \\sqrt{1 + \\sinh^2(y)}$, temos $\\frac{1}{\\sqrt{x^2 + 1}}$."
        ],
        sp.acosh(x): [
            "• **Dedução via Derivação Implícita**: Seja $y = \\text{arccosh}(x) \\implies \\cosh(y) = x$.",
            "• Derivando implicitamente: $\\sinh(y) \\cdot y' = 1 \\implies y' = \\frac{1}{\\sinh(y)}$.",
            "• Utilizando a identidade $\\sinh(y) = \\sqrt{\\cosh^2(y) - 1}$, chegamos a $\\frac{1}{\\sqrt{x^2 - 1}}$."
        ],
        sp.atanh(x): [
            "• **Dedução via Derivação Implícita**: Seja $y = \\text{arctanh}(x) \\implies \\tanh(y) = x$.",
            "• Derivando implicitamente: $\\text{sech}^2(y) \\cdot y' = 1 \\implies y' = \\frac{1}{\\text{sech}^2(y)}$.",
            "• Como $\\text{sech}^2(y) = 1 - \\tanh^2(y)$, substituímos para obter $\\frac{1}{1 - x^2}$."
        ]
    }

    # Se a função f coincidir perfeitamente com um elemento da nossa tabela
    if f in deducoes_tabela:
        f_linha = sp.diff(f, x)
        passos.extend(deducoes_tabela[f])
        passos.append(f"• **Resultado Concluído**: $f'(x) = {sp.latex(f_linha)}$")
        return f_linha, passos

    # Regras Estruturais Genéricas para outras expressões compostas
    if f.is_Add:
        passos.append("• **Regra da Soma/Diferença**: Deriva-se cada termo individualmente.")
        for arg in f.args:
            passos.append(f"  - Derivada de ${sp.latex(arg)}$ é ${sp.latex(sp.diff(arg, x))}$")
    elif f.is_Mul:
        passos.append("• **Regra do Produto**: $(u \\cdot v)' = u'v + uv'$")
        u, v = f.args[0], sp.Mul(*f.args[1:])
        passos.append(f"  - $u = {sp.latex(u)} \\implies u' = {sp.latex(sp.diff(u, x))}$")
        passos.append(f"  - $v = {sp.latex(v)} \\implies v' = {sp.latex(sp.diff(v, x))}$")
    else:
        passos.append("• **Aplicação de Regras Gerais / Regra da Cadeia**: Desenvolvendo blocos internos e externos.")

    f_linha = sp.diff(f, x)
    f_linha_simp = sp.trigsimp(f_linha)
    
    passos.append(f"• **Resultado Simplificado**: $f'(x) = {sp.latex(f_linha_simp)}$")
    return f_linha_simp, passos

def formatar_passos_integral(step, nivel=0):
    """Converte a árvore de passos do SymPy manualintegrate em texto explicativo em LaTeX."""
    linhas = []
    indent = "  " * nivel
    tipo = type(step).__name__
    
    if tipo == 'ConstantRule':
        linhas.append(f"{indent}• **Regra da Constante**: $\\int {sp.latex(step.c)} \\, dx = {sp.latex(step.c)}x$")
    elif tipo == 'PowerRule':
        linhas.append(f"{indent}• **Regra da Potência**: $\\int x^n dx = \\frac{{x^{{n+1}}}}{{n+1}}$")
    elif tipo == 'AddRule':
        linhas.append(f"{indent}• **Regra da Soma**: Integrando termo a termo:")
        for substep in step.substeps:
            linhas.extend(formatar_passos_integral(substep, nivel + 1))
    elif tipo == 'URule':
        linhas.append(f"{indent}• **$u$-Substituição**: Faça $u = {sp.latex(step.u_var)}$ com $du = {sp.latex(step.u_dev)}\\,dx$")
        linhas.extend(formatar_passos_integral(step.substep, nivel + 1))
    elif tipo == 'PartsRule':
        linhas.append(f"{indent}• **Integração por Partes**: $\\int u \\, dv = uv - \\int v \\, du$")
        linhas.append(f"{indent}  - $u = {sp.latex(step.u)}$, $dv = {sp.latex(step.v_step)}$")
        linhas.extend(formatar_passos_integral(step.substep, nivel + 1))
    elif tipo == 'AlternativeRule':
        if step.alternatives:
            linhas.extend(formatar_passos_integral(step.alternatives[0], nivel))
        else:
            linhas.append(f"{indent}• **Técnica Específica/Tabela**: Aplicação de identidade ou substituição fundamental.")
    else:
        linhas.append(f"{indent}• **Técnica Específica/Tabela**: Aplicação de identidade ou substituição fundamental.")
        
    return linhas

@app.get("/calcular")
def calcular(
    expressao: str = "x**2 * sin(x)",
    x0: float = 1.0,
    a: float = 0.0,
    b: float = 3.14
):
    try:
        x = sp.Symbol("x")
        expressao_limpa = tratar_expressao(expressao)
        f = sp.sympify(expressao_limpa)
        
        # 1. Derivada e seus passos detalhados
        f_linha, passos_derivada = gerar_passos_derivada(f, x)
        
        # 2. Avaliação da Derivada no ponto x0
        status_ponto = "sucesso"
        try:
            val_x0 = f_linha.subs(x, x0)
            if val_x0 in (sp.oo, -sp.oo, sp.zoo) or val_x0.has(sp.nan):
                derivada_no_ponto = "⚠️ Indefinido / Indeterminado"
                status_ponto = "alerta"
            else:
                num = para_float_seguro(val_x0)
                derivada_no_ponto = str(num) if num is not None else "⚠️ Erro de conversão"
        except Exception:
            lim = sp.limit(f_linha, x, x0)
            if lim in (sp.oo, -sp.oo, sp.zoo) or lim.has(sp.nan):
                derivada_no_ponto = "⚠️ Indefinido"
                status_ponto = "alerta"
            else:
                num = para_float_seguro(lim)
                derivada_no_ponto = str(num) if num is not None else "⚠️ Indefinido"

        # 3. Integral Indefinida e seus passos
        F_integral = sp.integrate(f, x)
        try:
            arvore_passos = integral_steps(f, x)
            passos_integral = formatar_passos_integral(arvore_passos)
        except Exception:
            passos_integral = ["• Aplicação direta das regras de integração da tabela."]

        # 4. Integral Definida no Intervalo [a, b]
        try:
            area = sp.integrate(f, (x, a, b))
            if area in (sp.oo, -sp.oo, sp.zoo) or area.has(sp.nan):
                area_formatada = "⚠️ Integral Divergente no intervalo"
            else:
                num_area = para_float_seguro(area)
                area_formatada = str(num_area) if num_area is not None else "⚠️ Erro ao avaliar área"
        except Exception:
            area_formatada = "⚠️ Indefinido no intervalo indicado"

        return {
            "status": "sucesso",
            "derivada_latex": sp.latex(f_linha),
            "passos_derivada": passos_derivada,
            "derivada_no_ponto": derivada_no_ponto,
            "status_ponto": status_ponto,
            "integral_indefinida_latex": sp.latex(F_integral),
            "passos_integral": passos_integral,
            "area_definida": area_formatada
        }
    except Exception as e:
        return {"status": "erro", "detalhes": str(e)}