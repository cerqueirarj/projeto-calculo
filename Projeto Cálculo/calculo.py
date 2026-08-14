from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sympy as sp
from sympy.integrals.manualintegrate import manualintegrate, integral_steps

app = FastAPI()
@app.get("/")
def home():
    return FileResponse("Projeto Cálculo/index.html")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def gerar_passos_derivada(f, x):
    """Gera uma explicação didática dos passos da derivada."""
    passos = []
    
    # Verifica se é soma/subtração
    if f.is_Add:
        passos.append("• **Regra da Soma/Diferença**: Deriva-se cada termo individualmente.")
        for arg in f.args:
            passos.append(f"  - Derivada de ${sp.latex(arg)}$ é ${sp.latex(sp.diff(arg, x))}$")
    # Verifica se é produto
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
        f = sp.sympify(expressao)
        
        # 1. Derivada e seus passos
        f_linha = sp.diff(f, x)
        passos_derivada = gerar_passos_derivada(f, x)

        # 2. Avaliação da Derivada no ponto x0
        status_ponto = "sucesso"
        try:
            val_x0 = f_linha.subs(x, x0)
            
            # Checa se é infinito (oo, zoo), indefinição ou indeterminação (NaN)
            if val_x0 in (sp.oo, -sp.oo, sp.zoo) or val_x0.has(sp.nan):
                derivada_no_ponto = "⚠️ Indefinido / Indeterminado (Divisão por zero ou não derivável)"
                status_ponto = "alerta"
            else:
                val_num = float(val_x0.evalf())
                derivada_no_ponto = f"{round(val_num, 4)}"
        except Exception:
            # Caso a substituição direta falhe, calcula via Limite
            lim = sp.limit(f_linha, x, x0)
            if lim in (sp.oo, -sp.oo, sp.zoo) or lim.has(sp.nan):
                derivada_no_ponto = "⚠️ Indefinido (O limite no ponto tende ao infinito ou não existe)"
                status_ponto = "alerta"
            else:
                derivada_no_ponto = f"{round(float(lim.evalf()), 4)}"

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
                area_formatada = str(round(float(area.evalf()), 4))
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