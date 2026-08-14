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

    # 2. Equivalências (Aliases) - Substitui variações em PT/EN antes de qualquer coisa
    equivalencias = {
        'sen': 'sin',
        'tg': 'tan',
        'arctg': 'atan',
        'arctan': 'atan',
        'arcsen': 'asin',
        'arcsin': 'asin'
    }
    for termo, original in equivalencias.items():
        expr = re.sub(rf'\b{termo}\b', original, expr)

    # 3. Converte caracteres Unicode sobrescritos (ex: ², ³, etc.)
    padrao_sobrescritos = r'([\u00B2\u00B3\u00B9\u2070-\u209C]+)'
    def reemp_sobrescrito(match):
        texto = unicodedata.normalize('NFKC', match.group(1))
        return f"^({texto})"
    expr = re.sub(padrao_sobrescritos, reemp_sobrescrito, expr)

    # 4. Transforma '^' em '**'
    expr = expr.replace('^', '**')

    # Lista completa de funções para processamento
    funcoes = [
        'sinh', 'cosh', 'tanh', 'sech', 'csch', 'coth',
        'sin', 'cos', 'tan', 'asin', 'acos', 'atan', 
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
        if abs(res.imag) < 1e-9:  # Se a parte imaginária for desprezível
            return round(res.real, 4)
        return "⚠️ Resultado Complexo/Não Real"
    except Exception:
        return None

def gerar_passos_derivada(f, x):
    """Gera uma explicação didática dos passos da derivada."""
    passos = []
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
        passos.append("• **Aplicação Direta/Regra da Cadeia**: Aplicando as regras fundamentais de derivação.")

    f_linha = sp.diff(f, x)
    passos.append(f"• **Resultado Simplificado**: $f'(x) = {sp.latex(f_linha)}$")
    return passos

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
        linhas.extend(formatar_passos_integral(step.alternatives[0], nivel))
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
        
        # 1. Derivada e seus passos
        f_linha = sp.diff(f, x)
        passos_derivada = gerar_passos_derivada(f, x)

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
            "integral_latex": sp.latex(F_integral),
            "passos_integral": passos_integral,
            "area_definitida": area_formatada
        }
    except Exception as e:
        return {"status": "erro", "mensagem": str(e)}