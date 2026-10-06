"""Шаг 11. Презентация: 12 слайдов 16:9 → docs/uklad_slides.html (автономный файл) и docs/uklad_slides.pdf.

Цифры берутся из outputs/ при сборке, рисунки — из report/figures и docs/screenshots (встраиваются в файл).
PDF печатается headless-Chrome/Edge; если браузера нет, остаётся HTML.
"""
import base64
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
O = ROOT / "outputs"
D = ROOT / "docs"


def img(path: Path) -> str:
    mime = "image/png" if path.suffix == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def pct(x, d=0):
    return f"{x * 100:.{d}f}".replace(".", ",") + "%"


# ---------- числа ----------
eta = pd.read_csv(O / "interpret" / "external_eta2.csv", index_col=0)
dyn = pd.read_csv(O / "dynamics" / "variants.csv", index_col=0)
ind, evo = dyn.loc["независимо по месяцам"], dyn.loc["эволюционный KEFRiN, α=0.5"]
af = pd.read_csv(O / "dynamics" / "affect_alpha.csv")["alpha"].iloc[1:]
gap = json.load(open(O / "interpret" / "divergence_summary.json", encoding="utf-8"))
trs = json.load(open(O / "dynamics" / "transitions_summary.json", encoding="utf-8"))
ck = pd.read_csv(O / "choose_k" / "summary.csv").set_index("K")
raw = pd.read_csv(O / "method_comparison" / "icvi_raw.csv", index_col=0)
main, km = "KEFRiN-c (признаки+сеть)", "k-means (признаки)"
gnn = raw[raw.index.str.contains("GNN")]
vj = json.load(open(O / "validation" / "summary.json", encoding="utf-8"))
N = dict(
    ho_wage=pct(vj["held_out_wage_eta2"]), tr_sig=vj["transitions_p05"],
    eta_cafe=pct(eta.loc["share_cafe", "eta2"]), eta_cafe0=pct(eta.loc["share_cafe", "eta2_base_only"]),
    eta_food=pct(eta.loc["share_food", "eta2"]), eta_mob=pct(eta.loc["mobility_index", "eta2"]),
    sw_ind=pct(ind.switch_rate_month, 1), sw_evo=pct(evo.switch_rate_month, 2),
    a_lo=f"{af.min():.2f}".replace(".", ","), a_hi=f"{af.max():.2f}".replace(".", ","),
    gap23=f"{gap['spread_2023']:.0f}", gap24=f"{gap['spread_2024']:.0f}",
    ci=f"+{gap['spread_change_ci95'][0]:.1f}…+{gap['spread_change_ci95'][1]:.1f}".replace(".", ","),
    tr_dir=trs["directed"], h6=f"{ck.loc[6, 'hennig_min']:.2f}".replace(".", ","),
    h7=f"{ck.loc[7, 'hennig_min']:.2f}".replace(".", ","),
    boot=f"{raw.loc[main, 'bootstrap_ARI']:.2f}".replace(".", ","),
    boot_gnn=f"{gnn['bootstrap_ARI'].min():.2f}–{gnn['bootstrap_ARI'].max():.2f}".replace(".", ","),
    sw_main=f"{raw.loc[main, 'SW']:.2f}".replace(".", ","), sw_km=f"{raw.loc[km, 'SW']:.2f}".replace(".", ","),
    mq_main=f"{raw.loc[main, 'MQ']:.2f}".replace(".", ","), mq_km=f"{raw.loc[km, 'MQ']:.2f}".replace(".", ","),
)
F, S = ROOT / "report" / "figures", D / "screenshots"


def slide(title, body, kicker="", cls=""):
    k = f'<p class="k">{kicker}</p>' if kicker else ""
    return f'<section class="s {cls}">{k}<h2>{title}</h2>{body}<footer>Уклад · шесть экономик России</footer></section>'


def kpi(items):
    return '<div class="kpi">' + "".join(f"<div><b>{v}</b><span>{t}</span></div>" for v, t in items) + "</div>"


slides = [
    f'''<section class="s title"><div class="tt"><p class="kk">Трек «Кластеризация»</p><h1>Уклад</h1>
      <p class="sub">шесть экономик России</p>
      <p class="sm">Кластеризация динамической атрибутированной сети 2 016 муниципалитетов · метод ДУЭТ</p>
      <p class="sm">Алиса Недозорова · ИТМО, «Инженерия искусственного интеллекта»</p></div></section>''',
    slide("Два взгляда на муниципалитет",
          '''<div class="two"><div class="card"><h3>Чем живёт</h3><p>Атрибуты узла: зарплата, население, доля горожан,
          доступность рынков, занятость по шести отраслям (Росстат, СберИндекс), уровень трат на жителя.</p></div>
          <div class="card"><h3>Как тратит</h3><p>Рёбра сети: два МО связаны, если похожи их траектории безналичных трат
          за 24 месяца (DTW, 15 ближайших соседей).</p></div></div>
          <p class="lead">Тип локальной экономики = группа МО, похожих и по экономической базе, и по образу трат.
          Одни и те же данные не учитываются дважды, поэтому вклад сети можно измерить.</p>''', "Идея"),
    slide("Данные",
          kpi([("2 016", "МО с полной историей трат"), ("24", "месяца, 2023–2024"), ("6", "категорий трат"),
               ("4", "источника: траты, Росстат, рынки, связи")]) +
          '''<p class="lead">СберИндекс: безналичные расходы по МО, индекс доступности рынков, автодорожные и
          железнодорожные связи, индекс покупательской мобильности. Росстат (БДПМО): зарплаты, население, занятость.
          Все файлы скачиваются скриптом с проверкой SHA-256.</p>''', "Что использовано"),
    slide("Метод ДУЭТ: четыре шага",
          '''<ol class="steps"><li><b>Разделение взглядов</b>атрибуты = база, рёбра = траты</li>
          <li><b>Совместная типология</b>KEFRiN: два центра у каждого типа, вес сети ξ</li>
          <li><b>Эволюционное отслеживание</b>24 помесячные сети, память α</li>
          <li><b>Протокол выбора</b>правило до сравнения + контрольная группа методов</li></ol>
          <p class="lead">DUal-view Evolutionary Typology. Блоки опираются на опубликованные работы (KEFRiN, эволюционная
          кластеризация, AFFECT), их сочетание и протокол проверки предложены в этой работе.</p>''', "Наш метод"),
    slide("Сеть: восемь правил ребра",
          f'''<div class="two"><img src="{img(S / '04_network.jpg')}" alt="Сеть МО">
          <div><p>Сравнены косинус профиля, гауссово ядро, корреляция рядов, лаговая корреляция, DTW, дороги,
          сходство экономической базы и их слияние SNF. Для каждого измерено, что оно связывает и как меняет типы.</p>
          <p>Выбран DTW: соседи по траектории трат похожи по зарплате (0,84), хотя зарплаты в рёбрах нет.</p></div></div>''',
          "Рёбра"),
    slide("13 методов, шесть индексов качества",
          f'''<div class="two"><img src="{img(S / '07_methods.jpg')}" alt="Карта компромисса методов">
          <div><p>8 методов в рейтинге выбора и 5 контрольных: графовые нейросети GAE, DAEGC, DMoN, Louvain, Ward
          со связностью. Индексы SW, CH, S_Dbw, AVI, AVU, MQ в z-оценках против случайной разметки.</p>
          <p><b>KEFRiN-c — первый</b> по Алескерову во всех 8 вариантах агрегирования; устойчив и к замене MQ на BasicMQ.</p>
          <p>Нейросети сильнее по модулярности, но неустойчивы: бутстрап {N['boot_gnn']} против {N['boot']}.</p></div></div>''',
          "Сравнение методов"),
    slide("Почему шесть типов",
          f'''<div class="two"><img src="{img(F / 'fig2_choose_k.png')}" alt="Выбор K">
          <div><p>K = 6 — наибольшее число типов, при котором <b>каждый</b> тип воспроизводится на подвыборках МО.</p>
          {kpi([(N['h6'], "худший тип при K = 6"), (N['h7'], "худший тип при K = 7")])}
          <p class="sm">Жаккар Хеннига, порог устойчивости 0,75.</p></div></div>''', "Выбор K"),
    slide("Шесть типов локальных экономик",
          f'''<img class="wide" src="{img(F / 'fig1_type_maps.png')}" alt="Карта типов">
          <p class="lead">Столичные агломерации и центры услуг · ресурсные территории Севера и Востока · промышленные и
          крупные города · транспортные узлы · районы бюджетной экономики · аграрные районы.</p>''', "Результат"),
    slide("Типы экономически осмысленны",
          kpi([(N['eta_cafe'], "разброса доли общепита объясняет тип"), (N['eta_food'], "разброса доли продовольствия"),
               (N['ho_wage'], "зарплаты объясняют типы, построенные БЕЗ зарплаты"), (N['eta_mob'], "индекса мобильности (внешний)")]) +
          f'''<p class="lead">Контрольная типология построена только по Росстату, без единой цифры о тратах, и объясняет
          структуру трат почти так же ({N['eta_cafe0']}), а типы без зарплаты в признаках всё равно объясняют зарплату: проверка не замкнута на модель.
          Индекс покупательской мобильности в построении типов не участвовал.</p>''', "Внешняя проверка"),
    slide("Динамика без шума",
          f'''<div class="two"><img src="{img(F / 'fig5_switches.png')}" alt="Смены типа по месяцам">
          <div>{kpi([(N['sw_evo'], "МО меняют тип за месяц"), (N['sw_ind'], "без памяти"), (str(N['tr_dir']), "МО сменили тип насовсем")])}
          <p>Память α = 0,5 проверена на синтетике с известной истиной и подтверждена AFFECT, который сам выбирает
          α от {N['a_lo']} до {N['a_hi']}.</p></div></div>''', "24 помесячные сети"),
    slide("Кто уходит в отрыв и ритм года",
          f'''<div class="two"><div>{kpi([(f"{N['gap23']} → {N['gap24']} п. п.", "разрыв трат между крайними типами"), (N['ci'], "95% бутстрап-интервал изменения")])}
          <p>Богатые типы уходят вперёд, бедные отстают сильнее.</p></div>
          <div><p><b>290 МО</b> со своим сезонным ритмом, повторившимся в оба года. Арктический июль: траты +17%,
          общепит +43%, продукты почти не растут, то есть это сезонный приток людей, а не завоз.</p>
          <p class="sm">Каждая трактовка проверена составом корзины в пиковый месяц.</p></div></div>''', "Выводы"),
    slide("Сервис и воспроизводимость",
          f'''<div class="two"><img src="{img(S / '03_atlas.jpg')}" alt="Атлас">
          <div><p>Лендинг одним файлом: атлас по месяцам, паспорт любого МО с экономическими двойниками, переход
          «карта → сеть», динамика, сравнение методов.</p>
          <p>Весь конвейер: <code>python scripts/run.py</code>. Seed, SHA-256 данных и результатов, 30 тестов, проверка
          с нуля в свежей копии репозитория.</p>
          <p class="sm">Отчёт: report/uklad_methodology.pdf · приложения: report/uklad_appendix.md</p></div></div>''',
          "Итог"),
]

CSS = """@page{size:1280px 720px;margin:0}*{box-sizing:border-box}body{margin:0;font-family:'Segoe UI',system-ui,sans-serif;color:#0f1712;background:#fff}
.s{width:1280px;height:720px;padding:56px 72px 48px;position:relative;overflow:hidden;page-break-after:always;background:linear-gradient(160deg,#ffffff 60%,#eef7f0)}
.s h2{font-size:40px;margin:0 0 26px;letter-spacing:-.01em}.k{color:#21a038;font-weight:700;letter-spacing:.18em;text-transform:uppercase;font-size:14px;margin:0 0 8px}
.s footer{position:absolute;left:72px;bottom:22px;font-size:13px;color:#85908a}.s p{font-size:20px;line-height:1.45;color:#2b3530;margin:0 0 14px}
.lead{font-size:22px!important}.sm{font-size:15px!important;color:#6a756f!important}
.two{display:grid;grid-template-columns:1.15fr 1fr;gap:36px;align-items:start}.two img{width:100%;border-radius:14px;box-shadow:0 8px 28px rgba(0,0,0,.12)}
img.wide{width:100%;max-height:430px;object-fit:contain;margin-bottom:12px}
.card{background:#f3f8f4;border-radius:16px;padding:22px 26px}.card h3{margin:0 0 8px;font-size:26px;color:#107f3a}
.kpi{display:flex;gap:16px;margin:6px 0 22px;flex-wrap:wrap}.kpi div{background:#f3f8f4;border-radius:14px;padding:16px 20px;min-width:180px;flex:1}
.kpi b{display:block;font-size:34px;color:#21a038}.kpi span{font-size:15px;color:#4a5650}
.steps{list-style:none;padding:0;margin:0 0 24px;display:grid;grid-template-columns:repeat(4,1fr);gap:16px;counter-reset:n}
.steps li{background:#f3f8f4;border-radius:16px;padding:20px;font-size:17px;color:#4a5650;counter-increment:n}
.steps li::before{content:counter(n);display:block;font-size:40px;font-weight:800;color:#21a038}.steps b{display:block;font-size:20px;color:#0f1712;margin-bottom:6px}
code{background:#eef3f0;padding:2px 6px;border-radius:6px;font-size:17px}
.title{padding:0;background:radial-gradient(ellipse at 50% 45%,#0f2a18 0%,#070d0a 60%,#030605 100%)}
.title .tt{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}
.title h1{font-family:'Ruslan Display',serif;font-weight:400;font-size:200px;line-height:1;margin:0;color:#42c661;text-shadow:0 8px 60px rgba(46,194,76,.45)}
.title .kk{font-family:'Prata',serif;color:#8fe3a0!important;letter-spacing:.3em;text-transform:uppercase;font-size:16px!important;margin:0 0 18px}
.title .sub{font-family:'Prata',serif;color:#b4beb8!important;font-size:34px!important;margin:16px 0 40px}
.title .sm{color:#85908a!important;font-size:17px!important;margin:0 0 6px}"""

FONTS = "".join(f"@font-face{{font-family:'{n}';src:url(data:font/woff2;base64,{base64.b64encode((ROOT / 'site_src' / 'fonts' / f).read_bytes()).decode()}) format('woff2')}}"
                for n, f in [("Ruslan Display", "ruslan-uklad.woff2"), ("Prata", "prata-intro.woff2")])
CSS = FONTS + CSS
html = f"<!doctype html><html lang='ru'><head><meta charset='utf-8'><title>Уклад: презентация</title><style>{CSS}</style></head><body>{''.join(slides)}</body></html>"
out = D / "uklad_slides.html"
out.write_text(html, encoding="utf-8")
print(f"{out.relative_to(ROOT)}: {len(slides)} слайдов")
browser = next((p for p in [shutil.which("chrome"), r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"] if p and Path(p).exists()), None)
if browser:
    pdf = D / "uklad_slides.pdf"
    subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf}",
                    out.as_uri()], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
    print(f"{pdf.relative_to(ROOT)}: {pdf.stat().st_size / 1e6:.1f} МБ")
