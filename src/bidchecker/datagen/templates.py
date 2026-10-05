"""固定体例 Markdown 渲染（plan/05 §1.1，体例即 M2 解析接口）。

行级格式契约（M2 解析器按此提取，改一行即破坏口径）：
- 头部键值行：`项目编号：` `项目名称：` `招标人：` `招标代理机构：` `投标人：` `采购类别：`
  （全角冒号；采购类别值"货物/服务"即 M3 only_if 类目门控关键词）；
- 日期时间一律 `YYYY-MM-DD HH:MM`；纯日期 `YYYY-MM-DD`；
- 资格证明行：`证明材料：<名称>｜编号：<号>｜有效期至：<日期|不限>｜等级：<等级|不限>`
  （全角｜分隔，M2 按｜切四槽）；
- 星号条款行：`★ S1：<text>。` / `▲ S2：<text>。`（第五章）；响应行 `S1：响应。<quote>`
  （第四章）；偏差表行 `S1：无偏离`（第三章，同前缀靠章节树区分）；
- 报价块：`投标总价（大写）：人民币<w>` / `投标总价（小写）：￥<n>` / `- <名>：￥<n>` /
  `分项合计：￥<n>`；金额渲染统一 render_amount（千分位+两位小数）；
- 人员/业绩行：`人员：<名>｜证书名称：<名>｜证书编号：<号>｜有效期至：<日期|不限>` /
  `业绩：<名>｜合同金额：￥<n>｜签订日期：<日>｜合同对方：<名>`；
- 招标 6 章 / 投标 7 章标题固定（`## 第X章 …`），章数与章名是解析器的章节树锚点。

D11 围标痕迹的落点：模板句挂第四章末尾、编制时间戳挂第六章署名区（干净对照组
各投标时间戳互不相同，围标对被注入为同一字符串——差异即证据）。
"""
from __future__ import annotations

from typing import Dict, List

from bidchecker.amounts import render_amount
from bidchecker.datagen.spec import BidBundle, ProjectBundle
from bidchecker.schema import BidCard, TenderCard

CATEGORY_LABEL = {"goods": "货物", "services": "服务"}

FOOTNOTE = "——本文件由 bidchecker datagen 合成生成（seed={seed}），全部主体、编号与证书均为虚构，仅用于系统评测。——"


def _amt(yuan) -> str:
    return render_amount(int(yuan))


# ---------------------------------------------------------------- 招标文件（6 章）
def render_tender(bundle: ProjectBundle) -> str:
    t: TenderCard = bundle.tender
    label = CATEGORY_LABEL[bundle.category]
    dates = t.key_dates
    issue_start = dates.issue_start[:10]
    issue_end = (bundle.meta["issue_end"])
    lines: List[str] = [
        f"# {t.project.name} 招标文件",
        "",
        f"项目编号：{t.project.number}",
        f"项目名称：{t.project.name}",
        f"招标人：{t.project.buyer}",
        f"招标代理机构：{t.project.agency}",
        f"采购类别：{label}",
        "",
        "## 第一章 招标公告",
        "",
        "### 1.1 项目概况",
        "",
        f"本项目已具备招标条件，现对{bundle.meta['subject']}进行公开招标，欢迎符合资格要求的"
        "投标人参加投标。",
        f"最高限价（预算金额）：{_amt(bundle.meta['budget_cap'])}。",
        f"投标有效期：自投标截止之日起{dates.validity_days}日历天。",
        "",
        "### 1.2 投标人资格要求",
        "",
    ]
    cat_label = {"qualification": "资格类", "finance": "财务类",
                 "performance": "业绩类", "personnel": "人员类"}
    for q in t.qualifications:
        level = f"，等级要求：{q.level}" if q.level else ""
        lines.append(f"{q.item_id}. {q.requirement}（{cat_label[q.category]}{level}）；")
    lines += [
        "",
        "### 1.3 招标文件的获取与递交",
        "",
        f"招标文件获取时间：{issue_start} 09:00 至 {issue_end} 17:00。",
        f"投标文件递交截止时间（投标截止时间）：{dates.submit_deadline}。",
        f"开标时间：{dates.open_time}。",
        "",
        "## 第二章 投标人须知",
        "",
        "### 2.1 投标人须知前附表",
        "",
        "| 条款名称 | 内容 |",
        "|---|---|",
        f"| 项目编号 | {t.project.number} |",
        f"| 投标截止时间 | {dates.submit_deadline} |",
        f"| 开标时间 | {dates.open_time} |",
        f"| 投标有效期 | {dates.validity_days}日历天 |",
        (f"| 投标保证金 | 金额：{_amt(t.bond.amount)}；形式：{'、'.join(t.bond.forms)}；"
         f"缴纳截止时间：{t.bond.deadline} |"),
        "",
        "### 2.2 否决投标条款",
        "",
    ]
    for r in t.rejection_clauses:
        lines.append(f"{r.item_id}. {r.text}")
    lines += [
        "",
        "### 2.3 须知正文",
        "",
        "2.3.1 投标人应认真阅读招标文件全部内容，按第六章格式要求编制并递交投标文件。",
        "2.3.2 投标文件应密封并在投标截止时间前送达指定地点，逾期送达的将被拒收。",
        "",
        "## 第三章 评标办法",
        "",
        "### 3.1 评标方法",
        "",
        f"评标方法：{t.scoring.method}。",
        "",
        "### 3.2 分值构成",
        "",
        "| 评分项 | 分值 |",
        "|---|---|",
    ]
    for item in t.scoring.items:
        lines.append(f"| {item.name} | {int(item.weight)} |")
    lines += [
        f"价格分权重：{int(t.scoring.price_weight)}%。",
        "",
        "## 第四章 合同条款",
        "",
        "4.1 付款方式：项目验收合格后支付合同总价的95%，剩余5%于质保期满后无息支付。",
        f"4.2 {'交货' if bundle.category == 'goods' else '服务'}地点：招标人指定地点。",
        "4.3 本合同条款为体例占位内容，具体以双方签订的合同为准。",
        "",
        "## 第五章 技术要求",
        "",
        "### 5.1 实质性要求（星号条款）",
        "",
    ]
    for c in t.star_clauses:
        lines.append(f"{c.marker} {c.item_id}：{c.text}。")
    lines += [
        "",
        "### 5.2 一般技术要求",
        "",
        f"5.2.1 所供{label}应符合国家相关标准及行业规范。",
        "5.2.2 投标人应对技术要求逐条应答，未逐条应答的视为不响应。",
        "",
        "## 第六章 投标文件格式",
        "",
        "6.1 投标文件应包含：投函声明、资格证明文件、商务偏差表、技术方案、"
        "开标一览表与分项报价、承诺函、拟投入人员与类似业绩清单。",
        "",
        FOOTNOTE.format(seed=bundle.seed),
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- 投标文件（7 章）
def render_bid(bundle: ProjectBundle, bb: BidBundle) -> str:
    b: BidCard = bb.card
    label = CATEGORY_LABEL[bundle.category]
    extras = bb.extras
    extras.setdefault("compile_ts", "2026-10-14 17:30")
    lines: List[str] = [
        f"# {b.project.name} 投标文件",
        "",
        f"项目编号：{b.project.number}",
        f"项目名称：{b.project.name}",
        f"投标人：{b.bidder}",
        f"采购类别：{label}",
        "",
        "## 第一章 投函声明",
        "",
        f"致：{b.project.buyer}",
        "1. 我方已仔细研究本项目招标文件的全部内容，自愿参加本项目投标，并完全接受"
        "招标文件中的实质性要求。",
        "2. 我方确认本投标文件所附各项资料真实、准确、完整。",
        "3. 本投标函自签署之日起生效，与我方投标文件具有同等效力。",
        f"投标人（盖章）：{b.bidder}",
        f"法定代表人或授权代表（签字）：{extras['signer']}",
        "",
        "## 第二章 资格证明文件",
        "",
    ]
    for q in b.qualifications:
        valid = q.valid_until or "不限"
        level = q.level or "不限"
        lines.append(f"证明材料：{q.requirement}｜编号：{extras['cert_nos'][q.item_id]}"
                     f"｜有效期至：{valid}｜等级：{level}")
    lines += [
        "（说明：以上证明材料复印件加盖公章，原件备查。）",
        "",
        "## 第三章 商务偏差表",
        "",
    ]
    for r in b.star_responses:
        lines.append(f"{r.star_id}：{r.deviation or '无偏离'}")
    lines += [
        "（说明：我方对招标文件全部条款均完全响应，无任何偏差。）",
        "",
        "## 第四章 技术方案（含星号条款响应）",
        "",
        "### 4.1 星号条款响应",
        "",
    ]
    by_id = {r.star_id: r for r in b.star_responses}
    for c in bundle.tender.star_clauses:
        r = by_id.get(c.item_id)
        if r is not None:
            lines.append(f"{c.item_id}：{r.quote}")
    lines += [
        "",
        "### 4.2 实施方案",
        "",
        "4.2.1 我方将成立专项项目组，按招标文件要求组织实施，并全程接受招标人监督。",
    ]
    sentence = extras.get("template_sentence")
    if sentence:
        lines += [sentence]
    prices = b.prices
    lines += [
        "",
        "## 第五章 开标一览表与分项报价",
        "",
        f"投标总价（大写）：人民币{prices.total_words}",
        f"投标总价（小写）：{_amt(prices.total_number)}",
        "分项报价：",
    ]
    for p in prices.items:
        lines.append(f"- {p.name}：{_amt(p.amount)}")
    lines.append(f"分项合计：{_amt(prices.items_sum)}")
    lines += [
        "",
        "## 第六章 承诺函",
        "",
        f"致：{b.project.buyer}",
        "我方郑重承诺：",
        f"1. 投标有效期为自投标截止之日起{b.key_dates.validity_days}日历天。",
        (f"2. 我方已按招标文件要求缴纳投标保证金{_amt(b.bond_response.amount)}，"
         f"缴纳形式：{'、'.join(b.bond_response.forms)}，凭证号：{extras['voucher_no']}。"),
        "3. 我方对招标文件全部内容无异议，所提供资料真实、完整、有效。",
        f"投标人（盖章）：{b.bidder}",
        f"编制完成时间：{extras['compile_ts']}",
        "",
        "## 第七章 拟投入人员与类似业绩清单",
        "",
        "拟投入人员：",
    ]
    for p in b.personnel:
        valid = p.valid_until or "不限"
        lines.append(f"- 人员：{p.name}｜证书名称：{p.cert_name}｜证书编号：{p.cert_no}"
                     f"｜有效期至：{valid}")
    lines.append("类似业绩：")
    if b.performance:
        for perf in b.performance:
            lines.append(f"- 业绩：{perf.name}｜合同金额：{_amt(perf.amount)}"
                         f"｜签订日期：{perf.date}｜合同对方：{perf.counterparty}")
    else:
        lines.append("- （无）")
    lines += [
        "",
        FOOTNOTE.format(seed=bundle.seed),
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_tender", "render_bid", "CATEGORY_LABEL"]
