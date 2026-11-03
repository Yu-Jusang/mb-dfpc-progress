"""Build index.html: live progress of the MB-DFPC revision study.

Reads the study folder (step marker files, suite manifests and unit files, benchmark logs,
frozen selections, validation summaries) and writes one static page in the KCB / galaxy
work-log style. Only progress, counts and fixed decisions are shown; result tables, code and
data stay in the study folder until the report is finished.
usage: python build.py
"""
import html
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

SITE = Path(__file__).resolve().parent
STUDY = Path(r"C:\Users\ggnat\Documents\Claude\2026-10-31\pc_blanket_study")
KST = timezone(timedelta(hours=9))
WEEK = "월화수목금토일"

SUITES = [  # folder, label, datasets, runs per dataset (schedules x arms) as text
    ("dev_thr", "threshold 개발 (개발용 시드)", 120, "1 schedule × 11 threshold"),
    ("fastcheck_main", "빠른 ridge 동일성 · main", 240, "4 schedule × 2"),
    ("fastcheck_stress", "빠른 ridge 동일성 · t5", 80, "4 schedule × 2"),
    ("fastcheck_large", "빠른 ridge 동일성 · p=50/100", 80, "4 schedule × 2"),
    ("fastcheck_kci", "빠른 ridge 동일성 · KCI", 40, "2 schedule × 1"),
    ("rs_main", "무작위 schedule · main (Gaussian)", 240, "30 schedule × 11 방법"),
    ("rs_stress", "무작위 schedule · t5 오차", 80, "30 schedule × 11 방법"),
    ("rs_large", "무작위 schedule · p=50/100", 80, "20 schedule × 11 방법"),
    ("rs_kci", "무작위 schedule · KCI 비선형", 40, "20 schedule × 11 방법"),
]
STATE_KO = {"done": "완료", "running": "진행 중", "queued": "대기", "failed": "실패"}
STATE_TAG = {"done": "tag-server", "running": "tag-local", "queued": "tag-none", "failed": "tag-both"}


def esc(s):
    return html.escape(str(s))


def now():
    return datetime.now(KST)


def mtime(rel):
    f = STUDY / rel
    return datetime.fromtimestamp(f.stat().st_mtime, KST) if f.exists() else None


def manifest_complete(rel):
    f = STUDY / rel
    if not f.exists():
        return False
    try:
        return bool(json.loads(f.read_text(encoding="utf-8")).get("complete"))
    except Exception:
        return False


def tag(state):
    return f'<span class="tag {STATE_TAG[state]}">{STATE_KO[state]}</span>'


def step_states():
    steps = json.loads((SITE / "data" / "steps.json").read_text(encoding="utf-8"))
    out = []
    for s in steps:
        st, t = s.get("status"), None
        if st == "auto":
            if "auto_done_all" in s:
                fin = all(manifest_complete(r) for r in s["auto_done_all"])
                t = max((mtime(r) for r in s["auto_done_all"] if mtime(r)), default=None) if fin else None
            else:
                fin = bool(mtime(s["auto_done"])) and (not s["auto_done"].endswith("manifest.json") or manifest_complete(s["auto_done"]))
                t = mtime(s["auto_done"]) if fin else None
            started = bool(s.get("auto_start") and mtime(s["auto_start"]))
            st = "done" if fin else ("running" if started else "queued")
        out.append(dict(s, state=st, t=t))
    # a step whose successor has started is at least running
    return out


def suite_rows():
    rows = []
    for folder, label, total, shape in SUITES:
        d = STUDY / "results_rev" / folder
        n = len(list((d / "units").glob("*.json"))) if (d / "units").exists() else 0
        st = "done" if manifest_complete(f"results_rev/{folder}/manifest.json") else ("running" if (d / "manifest.json").exists() else "queued")
        rows.append(dict(folder=folder, label=label, total=total, done=n, shape=shape, state=st))
    return rows


def bench_progress():
    out = []
    f = STUDY / "results_rev" / "bench" / "log_fisherz.txt"
    if f.exists():
        m = re.findall(r"^(\d+) / (\d+) ", f.read_text(encoding="utf-8", errors="ignore"), re.M)
        if m:
            out.append(("Fisher-Z microbenchmark", int(m[-1][0]), int(m[-1][1]), (STUDY / "results_rev/bench/fisherz_env.json").exists()))
    f = STUDY / "results_rev" / "bench" / "log_kci.txt"
    if f.exists():
        txt = f.read_text(encoding="utf-8", errors="ignore")
        m = re.findall(r"^timing (\d+) / (\d+)", txt, re.M)
        done = (STUDY / "results_rev/bench/kci_env.json").exists()
        out.append(("KCI microbenchmark", 700 if done else (int(m[-1][0]) if m else 0), 700, done))
    return out


def decisions():
    parts = []
    f = STUDY / "frozen_rev.json"
    if f.exists():
        z = json.loads(f.read_text(encoding="utf-8"))
        parts.append(("평가할 threshold 대안 (개발 데이터에서 고정)",
                      ", ".join(f"<code>{esc(t)}</code>" for t in z.get("thresholds", [])) +
                      f' <span class="muted small">· 고정 시각 {esc(z.get("written", ""))}</span>'))
    f = STUDY / "results_rev" / "validation_rev.json"
    if f.exists():
        v = json.loads(f.read_text(encoding="utf-8"))
        sm = sum(v.get("stored_matches", {}).values())
        parts.append(("사전 검증 통과", f"저장된 기존 실행 {sm}개 재현, memo 동일성 {v.get('memo_equal', 0)}건, "
                      f"추천 단계 동일성 {v.get('history_stage_identical', 0)}건, oracle 복원 {v.get('oracle_four', 0) + v.get('oracle_eight', 0)}건"))
    f = STUDY / "results_rev" / "trace" / "trace_counts.json"
    if f.exists():
        v = json.loads(f.read_text(encoding="utf-8"))
        parts.append(("경로 추적 대상", f"결과가 달라진 실행 중 {v.get('traced', 0)}건을 추적"))
    f = STUDY / "results_rev" / "costmodel" / "costmodel_summary.json"
    if f.exists():
        v = json.loads(f.read_text(encoding="utf-8"))
        parts.append(("선택된 비용 모델", f"Fisher-Z: {esc(v.get('fisherz_model'))} · KCI 조건부: {esc(v.get('kci_cond_model'))}"))
    return parts


def events(steps, suites):
    ev = []
    for s in steps:
        if s["state"] == "done" and s["t"]:
            ev.append((s["t"], f"{s['title']} 완료", ""))
    for r in suites:
        t = mtime(f"results_rev/{r['folder']}/manifest.json")
        if r["state"] == "done" and t:
            ev.append((t, f"{r['label']} 실행 완료", f"데이터셋 {r['total']}개, {r['shape']}"))
    lf = SITE / "data" / "log.json"
    if lf.exists():
        for e in json.loads(lf.read_text(encoding="utf-8")):
            ev.append((datetime.fromisoformat(e["t"]), e["title"], e.get("body", "")))
    ev.sort(key=lambda x: x[0], reverse=True)
    return ev


def sec(n, sid, title, body):
    return (f'<section id="{sid}" aria-labelledby="{sid}-h"><div class="sec-head"><span class="n">{n:02d}</span>'
            f'<h2 id="{sid}-h">{title}</h2></div>\n{body}\n</section>')


def build():
    t = now()
    steps = step_states(); suites = suite_rows(); bench = bench_progress()
    n_done = sum(s["state"] == "done" for s in steps)
    running = [s for s in steps if s["state"] == "running"]
    ds_done = sum(r["done"] for r in suites); ds_total = sum(r["total"] for r in suites)
    status = "완료" if n_done == len(steps) else "진행 중"
    nowf = SITE / "data" / "now.txt"
    now_txt = nowf.read_text(encoding="utf-8").strip() if nowf.exists() else ""
    start = mtime("design_revision.md")
    elapsed = (t - start) if start else None
    el_txt = f"{elapsed.seconds // 3600 + elapsed.days * 24}시간 {elapsed.seconds % 3600 // 60}분" if elapsed else "—"

    s1 = (f'<div class="formula" style="margin:0 0 18px;white-space:normal;font-family:inherit;line-height:1.75;overflow-wrap:anywhere">'
          f'<strong>지금 하는 일 ({t:%Y-%m-%d %H:%M} KST)</strong> — '
          + (", ".join(f"<strong>{esc(s['title'])}</strong>" for s in running) if running else "다음 단계를 준비하는 중") + ". "
          + esc(now_txt) + "</div>"
          '<dl class="deflist">'
          '<div><dt>연구</dt><dd>PC 계열 skeleton 탐색인 DF-PC 앞에 Markov blanket으로 겨냥한 추천 검정을 넣는 <strong>MB-DFPC</strong>를 보완하고, '
          '처음 읽는 독자를 위한 독립적인 영어 논문으로 개정합니다.</dd></div>'
          '<div><dt>추가 질문</dt><dd>① 추천 결과를 logical history에 즉시 기록하면 검정이 줄어드는가 ② 무작위 변수 순서 20–30개에서 결과가 얼마나 달라지는가 '
          '③ blanket threshold를 바꾸면 어떻게 되는가 ④ 조건집합 크기에 따른 검정 한 번의 실제 비용은 얼마이며, 그 기준으로 절감률이 유지되는가 '
          '⑤ ridge 구현 속도 차이를 없앤 공정한 실행시간 비교</dd></div>'
          '<div><dt>원칙</dt><dd>추가 실험은 설계와 평가 기준을 먼저 기록한 뒤 수행하고, 개발 데이터에서 고른 것은 독립 데이터에서만 평가합니다. 불리한 결과도 그대로 남깁니다.</dd></div>'
          '<div><dt>이 페이지</dt><dd>10분마다 자동 갱신됩니다. 진행 상황과 고정된 결정만 싣고, 결과 표·코드·자료는 보고서가 끝날 때까지 싣지 않습니다. '
          '시간 측정 중에는 측정에 영향을 주지 않도록 갱신을 쉽니다.</dd></div></dl>')

    srows = "".join(f'<tr><td class="num">{i:02d}</td><td><strong>{esc(s["title"])}</strong><br><span class="small muted">{esc(s["detail"])}</span></td>'
                    f'<td>{tag(s["state"])}</td><td class="num">{s["t"].strftime("%m-%d %H:%M") if s["t"] else "—"}</td></tr>'
                    for i, s in enumerate(steps, 1))
    s2 = ('<div class="table-wrap"><table><thead><tr><th scope="col" class="num">#</th><th scope="col">단계</th><th scope="col">상태</th>'
          '<th scope="col" class="num">완료</th></tr></thead><tbody>' + srows + '</tbody></table></div>')

    brows = "".join(f'<tr><td>{esc(name)}</td><td class="num">{a}/{b}</td><td>{tag("done" if fin else "running")}</td></tr>' for name, a, b, fin in bench)
    urows = "".join(f'<tr><td>{esc(r["label"])}</td><td class="mono small">{esc(r["shape"])}</td><td class="num">{r["done"]}/{r["total"]}</td><td>{tag(r["state"])}</td></tr>'
                    for r in suites)
    s3 = ('<h3>비용 측정</h3><div class="table-wrap"><table><thead><tr><th scope="col">측정</th><th scope="col" class="num">진행</th><th scope="col">상태</th></tr></thead><tbody>'
          + (brows or '<tr><td colspan="3" class="muted">아직 시작 전</td></tr>') + '</tbody></table></div>'
          '<h3>실험 suite</h3><div class="table-wrap"><table><thead><tr><th scope="col">suite</th><th scope="col">데이터셋당 실행</th><th scope="col" class="num">데이터셋</th>'
          '<th scope="col">상태</th></tr></thead><tbody>' + urows + '</tbody></table></div>'
          '<p class="small muted">한 데이터셋 안에서는 같은 query의 p-value를 한 번만 계산해 여러 실행이 나눠 씁니다. 각 실행의 검정 수는 따로 세며, 이 실행들의 시간은 쓰지 않고 별도의 순차 측정으로 잽니다.</p>')

    dec = decisions()
    s4 = ('<dl class="deflist">' + "".join(f"<div><dt>{esc(k)}</dt><dd>{v}</dd></div>" for k, v in dec) + "</dl>") if dec else \
        '<p class="muted">아직 고정된 결정이 없습니다. 사전 검증, threshold 선택, 비용 모델 선택이 끝나면 여기에 나타납니다.</p>'

    tl, day = [], None
    for tt, title, body in events(steps, suites):
        d = f"{tt:%Y. %m. %d} ({WEEK[tt.weekday()]})"
        if d != day:
            tl.append(f'<p class="tl-day">{d}</p>'); day = d
        tl.append(f'<article class="tl-item"><div class="tl-when"><time class="tl-time" datetime="{tt.isoformat()}">{tt:%H:%M}</time></div>'
                  f'<div class="tl-body"><div class="tl-head"><h3 class="tl-title">{esc(title)}</h3></div>'
                  f'<div class="tl-content"><p>{esc(body)}</p></div></div></article>')
    s5 = '<div class="timeline">' + "".join(tl) + "</div>" if tl else '<p class="muted">아직 기록이 없습니다.</p>'

    secs = [("s-now", "개요", s1), ("s-steps", "작업 단계", s2), ("s-runs", "실험 진행", s3),
            ("s-decisions", "고정된 결정·검증", s4), ("s-timeline", "타임라인", s5)]
    toc = "".join(f'<li><a href="#{sid}"><span class="n">{i:02d}</span>{t_}</a></li>' for i, (sid, t_, _) in enumerate(secs, 1))
    body = "\n".join(sec(i, sid, t_, b) for i, (sid, t_, b) in enumerate(secs, 1))
    art = (SITE / "assets" / "hero_art.html").read_text(encoding="utf-8")
    page = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta name="robots" content="noindex, nofollow">
<meta http-equiv="refresh" content="600">
<title>MB-DFPC 개정 연구 진행 현황</title>
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fontsource/jetbrains-mono@5.0.20/400.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fontsource/jetbrains-mono@5.0.20/500.css">
<link rel="stylesheet" href="assets/style.css">
</head>
<body data-project="causal">
<nav class="topbar" aria-label="주 메뉴"><div class="wrap wide"><a class="brand" href="./"><span class="mark" aria-hidden="true"></span><span class="brand-name">MB-DFPC 개정 연구</span></a><div class="nav-links"><a href="./" aria-current="page">진행 현황</a></div></div></nav>
<header class="hero">{art}<div class="wrap wide"><div class="hero-text"><nav class="crumbs" aria-label="경로"><span>인과 구조 학습</span><span aria-hidden="true"> / </span><span aria-current="page">MB-DFPC 개정</span></nav><div class="meta-row"><p class="eyebrow">Skeleton learning · 검정 비용과 순서 민감도</p><span class="status">{status}</span></div><h1>MB-DFPC 개정 연구 진행 현황</h1><p class="summary">캐시 정책 비교, 무작위 schedule 순서 민감도, blanket threshold, 검정 비용 모델, 공정한 실행시간 비교를 마치고 독립적인 영어 논문으로 다시 씁니다.</p><dl class="metrics"><div><dt>완료 단계</dt><dd>{n_done}/{len(steps)}</dd></div><div><dt>실험 데이터셋</dt><dd>{ds_done}/{ds_total}</dd></div><div><dt>설계 기록 후 경과</dt><dd>{el_txt}</dd></div></dl><p class="note">마지막 갱신 {t:%Y-%m-%d %H:%M} KST</p></div></div></header>
<div class="wrap wide layout"><nav class="toc" aria-label="목차"><ol>{toc}</ol></nav><main class="content">
{body}
</main></div>
<footer class="wrap wide"><p class="small muted">자동 생성 · build.py · {t:%Y-%m-%d %H:%M} KST</p></footer>
</body>
</html>
"""
    (SITE / "index.html").write_text(page, encoding="utf-8")
    print("built", n_done, len(steps), ds_done, ds_total)


if __name__ == "__main__":
    build()
