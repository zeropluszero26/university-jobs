# -*- coding: utf-8 -*-
"""Stage 3b — 从 index.html 解析在招岗位, 生成可售卖的每日求职资料包 PDF.

参数化: 改顶部 SRC / OUT / CN_DATE 即可复用。中文用 reportlab 内置 STSong-Light。
防御性过滤: 截止日 < 今天的卡片直接排除(无法解析的保留为灰色"待确认")。
"""
import re
import os
import datetime
from html import unescape

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
FONT = 'STSong-Light'

# ====================== CONFIG ======================
_BASE_DIR = os.environ.get('UJ_BASE_DIR', r'C:\Users\FEM\WorkBuddy\2026-05-08-task-5')
SRC = os.path.join(_BASE_DIR, 'index.html')
OUT = os.path.join(_BASE_DIR, '高校行政岗求职资料包-{DATE}.pdf')
# ====================================================

TODAY = datetime.date.today()
DATE_STR = TODAY.strftime('%Y-%m-%d')
CN_DATE = f'{TODAY.year}年{TODAY.month}月{TODAY.day}日'
OUT = OUT.format(DATE=DATE_STR)


def find_cards(html):
    cards, idx = [], html.find('<div class="job-card"')
    while idx != -1:
        end = html.find('>', idx)
        depth, i = 1, end + 1
        while i < len(html) and depth > 0:
            lt = html.find('<', i)
            if lt == -1:
                break
            if html.startswith('<div', lt):
                depth += 1
                i = lt + 4
            elif html.startswith('</div>', lt):
                depth -= 1
                i = lt + 6
                if depth == 0:
                    break
            else:
                i = lt + 1
        cards.append(html[idx:i])
        idx = html.find('<div class="job-card"', i)
    return cards


def g(card, pat, flags=0):
    m = re.search(pat, card, flags)
    return m.group(1).strip() if m else ''


def parse_card(card):
    school = g(card, r'<div class="school-name">(.*?)</div>')
    position = g(card, r'<div class="position-name">(.*?)</div>')
    hire = g(card, r'<span class="hire-type-badge[^"]*">([^<]*)</span>')
    vals = [re.sub(r'<[^>]+>', '', m).strip()
            for m in re.findall(r'<div class="info-item">(.*?)</div>', card, re.S)]
    headcount = vals[0] if len(vals) > 0 else ''
    education = vals[1] if len(vals) > 1 else ''
    salary = vals[2] if len(vals) > 2 else ''
    city = vals[3] if len(vals) > 3 else ''
    dl = re.search(r'<div class="deadline[^"]*">(.*?)</div>', card, re.S)
    deadline_text = re.sub(r'<[^>]+>', '', dl.group(1)).strip() if dl else ''
    url = g(card, r'<a href="([^"]+)"[^>]*class="apply-link"') or g(card, r"window\.open\('([^']+)'")
    region = g(card, r'data-region="([^"]+)"')
    is_new = 'new-badge' in card
    return dict(school=school, position=position, hire=hire, headcount=headcount,
                education=education, salary=salary, city=city, deadline_text=deadline_text,
                url=url, region=region, is_new=is_new)


def deadline_date(text):
    m = re.search(r'(\d{1,2})月(\d{1,2})日', text)
    if m:
        return datetime.date(2026, int(m.group(1)), int(m.group(2)))
    if any(k in text for k in ('长期', '招满', '有效')):
        return datetime.date(2099, 1, 1)
    return None


def deadline_color(text):
    d = deadline_date(text)
    if d is None:
        return colors.HexColor('#666666')
    if d.year == 2099:
        return colors.HexColor('#2980b9')
    return colors.HexColor('#c0392b') if (d - TODAY).days <= 3 else colors.HexColor('#27ae60')


def hire_color(hire):
    if '编制' in hire:
        return colors.HexColor('#8e44ad')
    if '聘用' in hire:
        return colors.HexColor('#2980b9')
    if '劳务' in hire or '派遣' in hire:
        return colors.HexColor('#d35400')
    return colors.HexColor('#555555')


def build():
    html = open(SRC, encoding='utf-8').read()
    jobs = [j for j in (parse_card(c) for c in find_cards(html)) if j['school'] and j['position']]
    before = len(jobs)
    jobs = [j for j in jobs if (lambda d: d is None or d >= TODAY)(deadline_date(j['deadline_text']))]
    print(f'Parsed jobs: {len(jobs)} (defensive dropped {before - len(jobs)} expired)')

    total, urgent, new = len(jobs), sum(1 for j in jobs if deadline_color(j['deadline_text']) == colors.HexColor('#c0392b')), sum(1 for j in jobs if j['is_new'])

    title = ParagraphStyle('title', fontName=FONT, fontSize=23, leading=30, alignment=TA_CENTER, textColor=colors.HexColor('#4a2c7a'))
    sub = ParagraphStyle('sub', fontName=FONT, fontSize=12, leading=18, alignment=TA_CENTER, textColor=colors.HexColor('#666666'))
    h2 = ParagraphStyle('h2', fontName=FONT, fontSize=14, leading=20, textColor=colors.HexColor('#4a2c7a'), spaceBefore=10, spaceAfter=6)
    body = ParagraphStyle('body', fontName=FONT, fontSize=9.5, leading=15, textColor=colors.HexColor('#333333'))
    cell = ParagraphStyle('cell', fontName=FONT, fontSize=8, leading=10.5)
    cellc = ParagraphStyle('cellc', fontName=FONT, fontSize=8, leading=10.5, alignment=TA_CENTER)
    head = ParagraphStyle('head', parent=cell, textColor=colors.white)
    headc = ParagraphStyle('headc', parent=cellc, textColor=colors.white)
    small = ParagraphStyle('small', fontName=FONT, fontSize=7, leading=9, textColor=colors.HexColor('#888888'))

    doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm, title=f'高校行政岗每日求职资料包 {DATE_STR}')
    E = []
    E.append(Spacer(1, 30))
    E.append(Paragraph('高校行政岗 · 每日求职资料包', title))
    E.append(Spacer(1, 8))
    E.append(Paragraph(f'{CN_DATE} 更新 · 仅含报名中岗位', sub))
    E.append(Spacer(1, 18))
    stat = Table([[Paragraph(f'<font size=20 color="#4a2c7a"><b>{total}</b></font><br/>在招岗位', cellc),
                   Paragraph(f'<font size=20 color="#c0392b"><b>{urgent}</b></font><br/>即将截止(≤3天)', cellc),
                   Paragraph(f'<font size=20 color="#27ae60"><b>{new}</b></font><br/>今日新增', cellc)]],
                 colWidths=[150, 150, 150])
    stat.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f3eefb')),
                              ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#d9c8f0')),
                              ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d9c8f0')),
                              ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 10),
                              ('BOTTOMPADDING', (0, 0), (-1, -1), 10)]))
    E.append(stat)
    E.append(Spacer(1, 16))
    E.append(Paragraph('本资料包由每日自动更新的高校行政岗招聘合集整理，覆盖全国一二线城市高校，'
                       '过期岗位已剔除，确保你看到的每一条都还在报名期。', body))
    E.append(Spacer(1, 8))
    E.append(Paragraph('整理人：5 年高校行政一线经验 —— 懂流程、懂门槛、懂你缺的哪一步。', body))
    E.append(Spacer(1, 8))
    E.append(Paragraph('⚠️ 本资料包仅供求职参考，最终以各校官方公告为准。', small))
    E.append(PageBreak())

    E.append(Paragraph('一、在招岗位明细', h2))
    E.append(Paragraph('（截止日期：红色=≤3天紧急，绿色=正常报名中，蓝色=长期/招满即止；点击「详情」跳转官方公告）', small))
    E.append(Spacer(1, 6))
    data = [[Paragraph('<b>学校</b>', headc), Paragraph('<b>岗位 / 薪资</b>', head),
             Paragraph('<b>地区·学历·人数</b>', head), Paragraph('<b>用工形式</b>', headc), Paragraph('<b>截止</b>', headc)]]
    for j in jobs:
        dc, hc = deadline_color(j['deadline_text']), hire_color(j['hire'])
        data.append([
            Paragraph(f"<b>{j['school']}</b><br/><font size=7 color='#888'>{j.get('region','')}</font>", cell),
            Paragraph(f"{j['position']}<br/><font size=7 color='#666'>薪资：{j['salary'] or '面议'}</font>"
                      + (f"<br/><a href='{j['url']}'><font size=7 color='#4a2c7a'>详情 ↗</font></a>" if j['url'] else ""), cell),
            Paragraph(f"{j['city']}<br/>{j['education']}<br/>招 {j['headcount']}", cell),
            Paragraph(f"<font color='{hc.hexval()}'><b>{j['hire']}</b></font>", cellc),
            Paragraph(f"<font color='{dc.hexval()}'><b>{j['deadline_text']}</b></font>", cellc)])
    tbl = Table(data, colWidths=[78, 158, 108, 52, 52], repeatRows=1)
    tbl.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a2c7a')),
                             ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                             ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                             ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e0d4f0')),
                             ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#faf7fe')]),
                             ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                             ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4)]))
    E.append(tbl)
    E.append(PageBreak())

    E.append(Paragraph('二、高校行政岗申请 · 实战提醒', h2))
    for k, v in [
        ('事业编制岗', '通常限应届/年龄（多数 35 岁以下），专业要求宽松但竞争激烈；务必核对「是否要求相应学科背景」。'),
        ('项目聘用 / 劳务派遣', '门槛更灵活、入职快，是转入高校主赛道的跳板；薪资多「按学校规定 / 一事一议」，面试时主动问清。'),
        ('简历核心', '突出行政流程实操、跨部门协调、公文写作、数据管理（如认证/招生系统）；用 STAR 讲清一件你牵头办成的事。'),
        ('截止前 1–2 天提交', '避开系统拥堵与材料补正风险；「招满即止」类岗位越早投越占优。'),
        ('信息核对', '本资料包已剔除过期岗位，但官方可能临时调整，投递前再点「详情」确认一次报名状态与材料清单。'),
    ]:
        E.append(Paragraph(f'• <b>{k}</b>：{v}', body))
        E.append(Spacer(1, 4))
    E.append(Spacer(1, 14))
    E.append(Paragraph('三、想第一时间拿到每日完整资料包？', h2))
    E.append(Paragraph('本资料包即 ¥9.9 单份产品，含当日全部在招岗位明细 + 申请实战贴士；'
                       '每日自动更新，购买后直接下载，无需进群。', body))
    E.append(Spacer(1, 4))
    E.append(Paragraph('小红书主页 / 评论区获取购买入口，或关注「高校行政岗招聘」持续更新。', body))

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont(FONT, 7.5)
        canvas.setFillColor(colors.HexColor('#999999'))
        canvas.drawString(18 * mm, 10 * mm, f'高校行政岗每日求职资料包 · {DATE_STR} · 仅供求职参考')
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, '第 %d 页' % d.page)
        canvas.restoreState()

    doc.build(E, onFirstPage=footer, onLaterPages=footer)
    print('PDF written:', OUT)
    return OUT


if __name__ == '__main__':
    build()
