#!/usr/bin/env python3
"""
build_dashboard.py - assemble an offline, self-contained personal finance
dashboard from an enriched transaction CSV and the same config files used by
enrich.py.

No network, no packages, no CDN. The output is one HTML file with inline data,
CSS, and JavaScript.
"""
import argparse, collections, datetime, html, json, os

import enrich


def ym(date_text):
    return str(date_text)[:7]


def amount(row):
    return enrich.money(row.get("amount"))


def month_sort_key(month):
    return month


def bucket_sum(rows, key_fn, value_fn):
    out = collections.defaultdict(float)
    for row in rows:
        out[key_fn(row)] += value_fn(row)
    return [{"name": k, "amount": round(v, 2)} for k, v in sorted(out.items())]


def build_data(rows, meta):
    rows = sorted(rows, key=lambda r: r["date"])
    spending_rows = [r for r in rows if amount(r) < 0 and r.get("spend_type") == "spend"]
    income_rows = [r for r in rows if amount(r) > 0]
    all_months = sorted({ym(r["date"]) for r in rows}, key=month_sort_key)
    current_month = all_months[-1] if all_months else ""
    current_rows = [r for r in rows if ym(r["date"]) == current_month]
    current_spend = [r for r in current_rows if amount(r) < 0 and r.get("spend_type") == "spend"]
    current_income = [r for r in current_rows if amount(r) > 0]

    monthly = []
    for month in all_months:
        mrows = [r for r in rows if ym(r["date"]) == month]
        spend = sum(abs(amount(r)) for r in mrows if amount(r) < 0 and r.get("spend_type") == "spend")
        income = sum(amount(r) for r in mrows if amount(r) > 0)
        monthly.append({"month": month, "spend": round(spend, 2),
                        "income": round(income, 2), "net": round(income - spend, 2)})

    categories = bucket_sum(spending_rows, lambda r: r.get("category") or "Other",
                            lambda r: abs(amount(r)))
    categories.sort(key=lambda r: -r["amount"])
    merchants = bucket_sum(spending_rows, lambda r: r.get("description") or "Unknown",
                           lambda r: abs(amount(r)))
    merchants.sort(key=lambda r: -r["amount"])
    income_sources = bucket_sum(income_rows, lambda r: r.get("description") or "Income",
                                lambda r: amount(r))
    income_sources.sort(key=lambda r: -r["amount"])
    daily = bucket_sum(spending_rows, lambda r: r["date"], lambda r: abs(amount(r)))

    recurring = meta.get("recurring", [])
    recurring_monthly = sum(r.get("monthly_cost", 0) for r in recurring if r.get("status") == "active")
    recent = list(reversed(rows[-12:]))
    dashboard = {
        "generatedAt": datetime.date.today().isoformat(),
        "overview": {
            "currentMonth": current_month,
            "transactions": len(rows),
            "spend": round(sum(abs(amount(r)) for r in current_spend), 2),
            "income": round(sum(amount(r) for r in current_income), 2),
            "net": round(sum(amount(r) for r in current_income) - sum(abs(amount(r)) for r in current_spend), 2),
            "recurringMonthly": round(recurring_monthly, 2),
            "liquidBalance": round(sum(a["balance"] for a in meta.get("accounts", []) if a.get("type") == "cash"), 2),
        },
        "netWorth": meta.get("netWorth", {}),
        "accounts": meta.get("accounts", []),
        "manualBalances": meta.get("manualBalances", []),
        "recurring": recurring,
        "spending": {
            "byCategory": categories,
            "byMerchant": merchants[:25],
            "byDay": daily,
            "incomeSources": income_sources,
        },
        "monthly": monthly,
        "transactions": rows,
        "recentTransactions": recent,
        "analytics": {
            "topCategory": categories[0] if categories else {"name": "None", "amount": 0},
            "highestMerchant": merchants[0] if merchants else {"name": "None", "amount": 0},
            "months": len(all_months),
            "averageMonthlySpend": round(sum(m["spend"] for m in monthly) / len(monthly), 2) if monthly else 0,
            "averageMonthlyIncome": round(sum(m["income"] for m in monthly) / len(monthly), 2) if monthly else 0,
        },
    }
    return dashboard


def data_script(data):
    return "window.FINANCE_DATA = %s;" % json.dumps(data, sort_keys=True)


CSS = r"""
:root{color-scheme:light dark;--bg:#f7f8f5;--panel:#ffffff;--ink:#20231f;--muted:#6f756b;--line:#dfe3d8;--accent:#2f6f73;--warn:#b45f3c}
@media (prefers-color-scheme:dark){:root{--bg:#151714;--panel:#20241f;--ink:#f0f2ec;--muted:#aab0a4;--line:#343a32;--accent:#8ac4bd;--warn:#e0a084}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
header{padding:28px 32px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:16px;align-items:flex-end}
h1{margin:0;font-size:26px;letter-spacing:0}h2{font-size:17px;margin:0 0 12px}main{padding:24px 32px 40px;display:grid;gap:22px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:16px;overflow:hidden}
.kpi{font-size:28px;font-weight:700}.muted{color:var(--muted)}.section{display:grid;gap:14px}.bar{height:10px;background:var(--line);border-radius:999px;overflow:hidden}.fill{height:100%;background:var(--accent)}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line);vertical-align:top}th{font-size:12px;color:var(--muted);font-weight:600}.right{text-align:right}.warn{color:var(--warn)}.tabs{display:flex;flex-wrap:wrap;gap:8px}.tabs button{border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:6px;padding:7px 10px;cursor:pointer}.tabs button.active{border-color:var(--accent);box-shadow:inset 0 0 0 1px var(--accent)}.screen{display:none}.screen.active{display:grid;gap:14px}.spark{display:flex;align-items:flex-end;height:70px;gap:3px}.spark span{display:block;flex:1;background:var(--accent);min-height:2px;border-radius:2px 2px 0 0}.pill{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:2px 8px;color:var(--muted);font-size:12px}
"""


JS = r"""
(function(){
const d=window.FINANCE_DATA;
const $=sel=>document.querySelector(sel);
const money=n=>(n||0).toLocaleString(undefined,{style:"currency",currency:"USD"});
const esc=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
function rows(items,cols){return `<table><thead><tr>${cols.map(c=>`<th class="${c.right?'right':''}">${c.h}</th>`).join("")}</tr></thead><tbody>${items.map(x=>`<tr>${cols.map(c=>`<td class="${c.right?'right':''}">${c.f(x)}</td>`).join("")}</tr>`).join("")}</tbody></table>`}
function bars(items,total){return items.map(x=>`<div><div style="display:flex;justify-content:space-between;gap:12px"><span>${esc(x.name)}</span><strong>${money(x.amount)}</strong></div><div class="bar"><div class="fill" style="width:${total?Math.min(100,x.amount/total*100):0}%"></div></div></div>`).join("")}
function spark(items,key){const max=Math.max(1,...items.map(x=>x[key]||0));return `<div class="spark">${items.map(x=>`<span title="${esc(x.month)} ${money(x[key])}" style="height:${Math.max(2,(x[key]||0)/max*100)}%"></span>`).join("")}</div>`}
function set(id,html){document.getElementById(id).innerHTML=html}
set("kpis",[
  ["Liquid balance",money(d.overview.liquidBalance)],["Net worth",money(d.netWorth.netWorth)],
  ["This month spend",money(d.overview.spend)],["Recurring monthly",money(d.overview.recurringMonthly)]
].map(x=>`<div class="card"><div class="muted">${x[0]}</div><div class="kpi">${x[1]}</div></div>`).join(""));
set("overview",`<div class="card"><h2>Monthly trend</h2>${spark(d.monthly,"spend")}</div><div class="card"><h2>Recent activity</h2>${rows(d.recentTransactions,[{h:"Date",f:x=>esc(x.date)},{h:"Description",f:x=>esc(x.description)},{h:"Category",f:x=>esc(x.category||"Other")},{h:"Amount",right:true,f:x=>money(x.amount)}])}</div>`);
set("networth",`<div class="grid"><div class="card"><h2>Assets</h2><div class="kpi">${money(d.netWorth.assets)}</div></div><div class="card"><h2>Liabilities</h2><div class="kpi">${money(d.netWorth.liabilities)}</div></div><div class="card"><h2>Net worth</h2><div class="kpi">${money(d.netWorth.netWorth)}</div></div></div><div class="card"><h2>Balance inputs</h2>${rows(d.manualBalances,[{h:"Account",f:x=>esc(x.account)},{h:"Type",f:x=>esc(x.type)},{h:"Balance",right:true,f:x=>money(x.balance)}])}</div>`);
const totalCat=d.spending.byCategory.reduce((s,x)=>s+x.amount,0);
set("spending",`<div class="grid"><div class="card"><h2>Categories</h2>${bars(d.spending.byCategory,totalCat)}</div><div class="card"><h2>Top merchants</h2>${rows(d.spending.byMerchant.slice(0,12),[{h:"Merchant",f:x=>esc(x.name)},{h:"Spend",right:true,f:x=>money(x.amount)}])}</div><div class="card"><h2>Income sources</h2>${rows(d.spending.incomeSources,[{h:"Source",f:x=>esc(x.name)},{h:"Amount",right:true,f:x=>money(x.amount)}])}</div></div>`);
set("recurring",`<div class="card">${rows(d.recurring,[{h:"Name",f:x=>esc(x.label)},{h:"Cadence",f:x=>`<span class="pill">${esc(x.cadence)}</span>`},{h:"Status",f:x=>x.status==="possibly_cancelled"?`<span class="warn">possibly cancelled</span>`:esc(x.status)},{h:"Monthly",right:true,f:x=>money(x.monthly_cost)},{h:"Last seen",f:x=>esc(x.last_seen)}])}</div>`);
set("accounts",`<div class="card">${rows(d.accounts,[{h:"Account",f:x=>esc(x.account)},{h:"Institution",f:x=>esc(x.institution)},{h:"Type",f:x=>esc(x.type)},{h:"Balance",right:true,f:x=>money(x.balance)},{h:"Transactions",right:true,f:x=>esc(x.transaction_count)}])}</div>`);
set("debt",`<div class="card">${rows(d.accounts.filter(x=>x.type==="credit"||x.type==="loan"),[{h:"Account",f:x=>esc(x.account)},{h:"Type",f:x=>esc(x.type)},{h:"Balance",right:true,f:x=>money(x.balance)},{h:"APR / payment",f:x=>"not provided"}])}</div>`);
set("transactions",`<div class="card">${rows(d.transactions,[{h:"Date",f:x=>esc(x.date)},{h:"Description",f:x=>esc(x.description)},{h:"Account",f:x=>esc(x.account)},{h:"Category",f:x=>esc(x.category||"Other")},{h:"Subcategory",f:x=>esc(x.subcategory)},{h:"Amount",right:true,f:x=>money(x.amount)}])}</div>`);
set("analytics",`<div class="grid"><div class="card"><h2>Average monthly spend</h2><div class="kpi">${money(d.analytics.averageMonthlySpend)}</div></div><div class="card"><h2>Average monthly income</h2><div class="kpi">${money(d.analytics.averageMonthlyIncome)}</div></div><div class="card"><h2>Top category</h2><div class="kpi">${esc(d.analytics.topCategory.name)}</div><div class="muted">${money(d.analytics.topCategory.amount)}</div></div></div><div class="card"><h2>Monthly data</h2>${rows(d.monthly,[{h:"Month",f:x=>esc(x.month)},{h:"Income",right:true,f:x=>money(x.income)},{h:"Spend",right:true,f:x=>money(x.spend)},{h:"Net",right:true,f:x=>money(x.net)}])}</div>`);
document.querySelectorAll(".tabs button").forEach(btn=>btn.addEventListener("click",()=>{document.querySelectorAll(".tabs button,.screen").forEach(x=>x.classList.remove("active"));btn.classList.add("active");document.getElementById(btn.dataset.screen).classList.add("active")}));
})();
"""


def render_html(data):
    title = "Money Map Dashboard"
    screens = [
        ("overview", "Overview"),
        ("networth", "Net Worth"),
        ("spending", "Spending"),
        ("recurring", "Recurring"),
        ("accounts", "Accounts"),
        ("debt", "Debt & Bills"),
        ("transactions", "Transactions"),
        ("analytics", "Analytics"),
    ]
    buttons = "\n".join('<button class="%s" data-screen="%s">%s</button>' %
                        ("active" if i == 0 else "", sid, html.escape(label))
                        for i, (sid, label) in enumerate(screens))
    sections = "\n".join('<section id="%s" class="screen %s"></section>' %
                         (sid, "active" if i == 0 else "") for i, (sid, _label) in enumerate(screens))
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{css}</style>
<script>{data}</script>
</head>
<body>
<header><div><h1>{title}</h1><div class="muted">Generated {generated}</div></div><nav class="tabs">{buttons}</nav></header>
<main><section id="kpis" class="grid"></section>{sections}</main>
<script>{js}</script>
</body>
</html>
""".format(title=html.escape(title), css=CSS, data=data_script(data),
           generated=html.escape(data.get("generatedAt", "")), buttons=buttons,
           sections=sections, js=JS)


def build(input_path, output_path, category_path, aliases_path, labels_path, balances_path):
    rows = enrich.read_csv(input_path)
    enriched, recurring = enrich.enrich_rows(
        rows,
        category_rules=enrich.load_rules(category_path),
        aliases=enrich.load_rules(aliases_path),
        labels=enrich.load_rules(labels_path),
    )
    manual_balances = enrich.load_manual_balances(balances_path)
    accounts, net_worth = enrich.summarize_accounts(enriched, manual_balances)
    meta = {"recurring": recurring, "manualBalances": manual_balances,
            "accounts": accounts, "netWorth": net_worth}
    data = build_data(enriched, meta)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(render_html(data))
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="input", required=True,
                    help="enriched or master transaction CSV")
    ap.add_argument("--out", default="Finance Dashboard.html")
    ap.add_argument("--categories", default=enrich.default_config_path("merchant_categories.example.csv"))
    ap.add_argument("--aliases", default=enrich.default_config_path("account_aliases.example.csv"))
    ap.add_argument("--labels", default=enrich.default_config_path("recurring_labels.example.csv"))
    ap.add_argument("--balances", default=enrich.default_config_path("manual_balances.example.csv"))
    args = ap.parse_args()
    data = build(args.input, args.out, args.categories, args.aliases,
                 args.labels, args.balances)
    print("WROTE %s (%d transactions, %d recurring)" %
          (args.out, len(data["transactions"]), len(data["recurring"])))


if __name__ == "__main__":
    main()
