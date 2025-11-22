from flask import Flask, request, jsonify, render_template
import re
from sympy import Symbol, Eq, solve, simplify, N, Rational
from sympy.parsing.sympy_parser import (
    parse_expr, standard_transformations,
    implicit_multiplication_application,
    convert_xor, function_exponentiation
)

app = Flask(__name__)

# Allowed symbols/functions
x = Symbol('x')
locals_map = {
    'x': x,
    'pi': __import__('sympy').pi,
    'e': __import__('sympy').E,
    'sin': __import__('sympy').sin,
    'cos': __import__('sympy').cos,
    'tan': __import__('sympy').tan,
    'asin': __import__('sympy').asin,
    'acos': __import__('sympy').acos,
    'atan': __import__('sympy').atan,
    'log': __import__('sympy').log,
    'ln': __import__('sympy').log,
    'sqrt': __import__('sympy').sqrt,
    'abs': __import__('sympy').Abs,
}

transformations = (
    standard_transformations
    + (implicit_multiplication_application, convert_xor, function_exponentiation)
)

def preprocess(expr: str) -> str:
    expr = expr.strip()
    expr = expr.replace('×','*').replace('÷','/').replace('−','-')
    expr = expr.replace(':','/')  # allow 10:3
    # percent: 12% -> (12/100)
    expr = re.sub(r'(\d+(?:\.\d+)?)\s*%', r'(\1/100)', expr)
    return expr

def parse_sympy(expr: str):
    expr = preprocess(expr)
    return parse_expr(expr, local_dict=locals_map, transformations=transformations, evaluate=True), expr

NL_FRACTION_KEYWORDS = (
    "в обычную", "в обыкновенную", "обычная дробь", "обыкновенная дробь",
    "to fraction", "fraction"
)

def handle_natural_language(raw: str):
    """
    Простенький обработчик русских текстовых запросов ИИ.
    Поддержка:
    - "дробь 3.8112 в обычную" -> 38112/10000 -> 4764/1250
    - "20 процентов от 150" -> 30
    Если не узнали паттерн -> None и дальше работает sympy.
    """
    low = raw.lower().strip()
    if not low:
        return None

    has_cyrillic = bool(re.search(r"[а-яё]", low))
    steps = []

    # 1) Десятичная дробь -> обыкновенная
    if has_cyrillic and "дроб" in low:
        m = re.search(r"-?\d+(?:[.,]\d+)?", low)
        if not m:
            return {"steps": ["Не нашёл число для перевода в дробь."], "result": "?"}

        num_str = m.group(0).replace(",", ".")
        steps.append(f"Нашёл число: {num_str}")

        if "." in num_str:
            digits = len(num_str.split(".")[1])
            pure = int(num_str.replace(".", ""))
            raw_frac = Rational(pure, 10**digits)
            simp = Rational(num_str)  # автоматически сокращается

            steps.append(f"{num_str} = {pure} / 10^{digits}")
            steps.append(f"Сокращаем дробь: {raw_frac} = {simp}")

            return {
                "steps": steps,
                "result": f"{simp.p}/{simp.q}"
            }
        else:
            steps.append("Число целое, переводить в дробь не нужно.")
            return {"steps": steps, "result": num_str}

    # 2) Проценты: "20 процентов от 150"
    if has_cyrillic and "процент" in low:
        m_per = re.search(r"(-?\d+(?:[.,]\d+)?)\s*процент", low)
        m_of = re.search(r"от\s+(-?\d+(?:[.,]\d+)?)", low)
        if m_per and m_of:
            a = float(m_per.group(1).replace(",", "."))
            b = float(m_of.group(1).replace(",", "."))
            steps.append(f"Проценты: {a}% от {b}")
            steps.append(f"Переводим проценты в число: {a}% = {a}/100")
            result_val = b * (a/100.0)
            steps.append(f"Вычисляем: {b} * {a}/100 = {result_val}")
            return {
                "steps": steps,
                "result": format_result(result_val)
            }

    # 3) "реши 2x+3=7" / "посчитай 2+2"
    if has_cyrillic and any(k in low for k in ("реши", "посчитай", "вычисли")):
        expr_part = None
        for kw in ("реши", "посчитай", "вычисли"):
            idx = low.find(kw)
            if idx != -1:
                expr_part = raw[idx+len(kw):].strip(" :,.")
                break
        if expr_part:
            steps.append(f"Выделяю выражение: {expr_part}")
            # Передадим дальше в обычный пайплайн, но уже без слов.
            return {
                "rewrite": expr_part,
                "steps": steps
            }

    return None

def format_result(val):
    """
    Красивый вывод:
    - целые без .0
    - обрезаем лишние нули
    - ограничиваем точность
    """
    if isinstance(val, float):
        f = val
        if abs(f - round(f)) < 1e-12:
            return str(int(round(f)))
        s = f"{f:.12g}"
        if re.match(r"^-?\d+\.\d+$", s):
            s = s.rstrip("0").rstrip(".")
        return s

    try:
        if val.is_number:
            num = N(val, 15)
            f = float(num)

            if abs(f - round(f)) < 1e-12:
                return str(int(round(f)))

            s = f"{f:.12g}"
            if re.match(r"^-?\d+\.\d+$", s):
                s = s.rstrip("0").rstrip(".")
            return s
    except Exception:
        pass

    s = str(val)
    if re.match(r"^-?\d+\.\d+$", s):
        s = s.rstrip("0").rstrip(".")
    return s

@app.route("/")
def index():
    return render_template("index.html")

@app.post("/api/calc")
def api_calc():
    data = request.get_json(force=True, silent=True) or {}
    raw = data.get("expression","")
    try:
        sym, cleaned = parse_sympy(raw)
        val = simplify(sym)
        return jsonify(result=format_result(val))
    except Exception as e:
        return jsonify(error=f"Не могу посчитать: {e}"), 400

@app.post("/api/assist")
def api_assist():
    data = request.get_json(force=True, silent=True) or {}
    raw = data.get("expression","")
    steps = []

    # Сначала пробуем понять текст по-русски
    nl = handle_natural_language(raw)
    if nl:
        if "rewrite" not in nl:
            return jsonify(steps=nl["steps"], result=nl["result"])
        steps.extend(nl.get("steps", []))
        raw = nl["rewrite"]

    try:
        cleaned_raw = preprocess(raw)
        steps.append(f"Исходное выражение: {raw}")
        steps.append(f"После нормализации: {cleaned_raw}")

        # Equation mode
        if "=" in cleaned_raw:
            left_s, right_s = cleaned_raw.split("=", 1)
            left = parse_expr(left_s, local_dict=locals_map, transformations=transformations, evaluate=True)
            right = parse_expr(right_s, local_dict=locals_map, transformations=transformations, evaluate=True)
            eq = Eq(left, right)
            steps.append(f"Уравнение: {eq}")
            sol = solve(eq, x, dict=True)
            if not sol:
                steps.append("Решений не найдено.")
                return jsonify(steps=steps, result="нет решений")
            sols = [s[x] for s in sol if x in s]
            steps.append(f"Решения: {sols}")
            return jsonify(steps=steps, result=str(sols))

        sym, _ = parse_sympy(raw)
        steps.append(f"Символьная форма: {sym}")

        simp = simplify(sym)
        steps.append(f"Упрощение: {simp}")

        result_str = format_result(simp)
        steps.append(f"Результат: {result_str}")

        return jsonify(steps=steps, result=result_str)
    except Exception as e:
        return jsonify(error=f"Ошибка разбора/решения: {e}"), 400

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)