#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage 2 — 生成高校行政岗招聘页面 (参数化模板).

流程: 读 index.html → 剔除过期(截止<=今天) → 合并当日新岗 → 去重排序 →
      渲染卡片 → 写回 index.html + archive/YYYY-MM-DD.html + stats json。

CONFIG 顶部集中修改; add_new_jobs() 由 Stage 1 发现草稿填充(见 SKILL.md)。
"""
import os
import re
import json
from datetime import datetime, timedelta
from html import escape

# ====================== CONFIG ======================
BASE_DIR = os.environ.get('UJ_BASE_DIR', r'C:\Users\FEM\WorkBuddy\2026-05-08-task-5')   # 工作目录(云端 Actions 用 UJ_BASE_DIR 覆盖为 checkout 目录)
FIRST_DATE = '2026-05-08'                                # 首页 JS 中保持不变
HERE = os.path.dirname(os.path.abspath(__file__))
# 当日新岗草稿(由 Stage 1 发现+核实后生成); 存在则自动合并, 缺失则无新公告
DRAFT_PATHS = [os.path.join(BASE_DIR, 'new_jobs_draft.json'),
               os.path.join(HERE, 'new_jobs_draft.json')]
# ====================================================

TODAY = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
PAGE_DATE = TODAY.strftime('%Y-%m-%d')

REGION_PRIORITY = {
    '华东': 1, '华北': 2, '华南': 3, '华中': 4, '西南': 5,
    '西北': 6, '东北': 7, '其他': 8,
}
CITY_TIER1 = {'北京', '上海', '广州', '深圳', '成都', '杭州', '武汉', '南京', '重庆',
              '天津', '苏州', '西安', '长沙', '郑州', '青岛', '大连', '厦门', '合肥',
              '宁波', '济南', '福州', '无锡', '昆明', '哈尔滨', '沈阳'}


def parse_deadline(text):
    text = (text or '').strip()
    m = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', text)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', text)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r'(\d{1,2})月(\d{1,2})日', text)
    if m:
        d = datetime(2026, int(m.group(1)), int(m.group(2)))
        if d < TODAY - timedelta(days=180):
            d = d.replace(year=2027)
        return d
    if any(k in text for k in ('长期', '招满即止', '详见正文', '有效', '招满')):
        return datetime(2099, 12, 31)
    return None


def fmt_deadline(d):
    if d.year == 2099:
        return '长期有效'
    if d.year == TODAY.year:
        return f'{d.month}月{d.day}日截止'
    return f'{d.year}-{d.month:02d}-{d.day:02d}截止'


def deadline_css(d):
    if d.year == 2099:
        return 'deadline-long', 'fa-infinity'
    if (d - TODAY).days <= 3:
        return 'deadline-urgent', 'fa-exclamation-triangle'
    return 'deadline-normal', 'fa-clock'


def region_of_city(city):
    city = city.replace('省', '').replace('市', '').replace('自治区', '')
    mapping = {'北京': '华北', '天津': '华北', '河北': '华北', '山西': '华北', '内蒙古': '华北',
               '上海': '华东', '江苏': '华东', '浙江': '华东', '安徽': '华东', '江西': '华东',
               '山东': '华东', '福建': '华东', '广东': '华南', '广西': '华南', '海南': '华南',
               '香港': '华南', '澳门': '华南', '湖北': '华中', '湖南': '华中', '河南': '华中',
               '四川': '西南', '重庆': '西南', '贵州': '西南', '云南': '西南', '西藏': '西南',
               '陕西': '西北', '甘肃': '西北', '青海': '西北', '宁夏': '西北', '新疆': '西北',
               '辽宁': '东北', '吉林': '东北', '黑龙江': '东北'}
    for prov, reg in mapping.items():
        if prov in city:
            return reg
    # 城市名直传兜底(省份匹配不到时, 按25个一二线主城+常见市映射)
    city_map = {'北京': '华北', '天津': '华北', '上海': '华东', '重庆': '西南',
                '广州': '华南', '深圳': '华南', '成都': '西南', '杭州': '华东',
                '武汉': '华中', '南京': '华东', '西安': '西北', '长沙': '华中',
                '郑州': '华中', '青岛': '华东', '大连': '东北', '厦门': '华东',
                '合肥': '华东', '宁波': '华东', '济南': '华东', '福州': '华东',
                '无锡': '华东', '昆明': '西南', '哈尔滨': '东北', '沈阳': '东北',
                '苏州': '华东', '清远': '华南', '东莞': '华南', '佛山': '华南'}
    for c, reg in city_map.items():
        if c in city:
            return reg
    return '其他'


def is_tier1(city):
    city = city.replace('市', '').replace('区', '')
    return any(c in city or city in c for c in CITY_TIER1)


class Job:
    def __init__(self, school, position, region, education, hire_type, headcount,
                 salary, deadline, city, url, position_type='行政管理', tags=None, is_new=False):
        self.school = school
        self.position = position
        self.region = region or region_of_city(city)
        self.education = education
        self.hire_type = hire_type
        self.headcount = headcount
        self.salary = salary
        self.deadline = deadline
        self.city = city
        self.url = url
        self.position_type = position_type
        self.tags = tags or []
        self.is_new = is_new

    def deadline_text(self):
        return fmt_deadline(self.deadline)

    def badge_class(self):
        ht = self.hire_type
        if '事业编制' in ht or '事业编' in ht:
            return 'badge-bianzhi'
        if '项目聘用' in ht or '聘用' in ht:
            return 'badge-pinyong'
        if '劳务派遣' in ht or '派遣' in ht:
            return 'badge-laowu'
        if '劳动合同' in ht or '合同' in ht:
            return 'badge-hetong'
        if '人事代理' in ht:
            return 'badge-beian'
        return 'badge-pinyong'


def extract_jobs_from_html(html):
    jobs = []
    starts = [m.start() for m in re.finditer(r'<div\s+class="job-card"', html)]
    for start in starts:
        try:
            open_end = html.find('>', start)
            attr_str = html[start+4:open_end]
            region = re.search(r'data-region="([^"]+)"', attr_str)
            education = re.search(r'data-education="([^"]+)"', attr_str)
            hire = re.search(r'data-hire="([^"]+)"', attr_str)
            position_type = re.search(r'data-position="([^"]+)"', attr_str)
            url = re.search(r"onclick=\"window\.open\('([^']+)',", attr_str)
            region = region.group(1) if region else '其他'
            education = education.group(1) if education else '本科'
            hire_type = hire.group(1) if hire else '劳务派遣'
            position_type = position_type.group(1) if position_type else '行政管理'
            url = url.group(1) if url else ''
            i = open_end + 1
            depth = 1
            while i < len(html) and depth > 0:
                if html[i:i+4] == '<div':
                    if re.match(r'<div\s|>', html[i:i+5]) or html[i+4] == '>':
                        depth += 1
                    i += 4
                elif html[i:i+6] == '</div>':
                    depth -= 1
                    if depth == 0:
                        break
                    i += 6
                else:
                    i += 1
            card = html[open_end+1:i]
            school = re.search(r'<div class="school-name">(.*?)</div>', card)
            school = school.group(1) if school else ''
            position = re.search(r'<div class="position-name">(.*?)</div>', card)
            position = position.group(1) if position else ''
            headcount = re.search(r'<i class="fas fa-users"></i>\s*<span class="value">(.*?)</span>', card)
            headcount = headcount.group(1) if headcount else '若干'
            salary = re.search(r'<i class="fas fa-yen-sign"></i>\s*<span class="value">(.*?)</span>', card)
            salary = salary.group(1) if salary else '面议'
            city = re.search(r'<i class="fas fa-building"></i>\s*<span class="value">(.*?)</span>', card)
            city = city.group(1) if city else ''
            dl = re.search(r'<div class="deadline[^"]*">.*?>(.*?)</div>', card, re.S)
            dl_text = re.sub(r'<i[^>]*></i>', '', dl.group(1)).strip() if dl else ''
            deadline = parse_deadline(dl_text)
            if deadline is None:
                continue
            tags = re.findall(r'<span class="tag[^"]*">(.*?)</span>', card)
            jobs.append(Job(school, position, region, education, hire_type, headcount,
                            salary, deadline, city, url, position_type, tags, is_new=False))
        except Exception as e:
            print('parse card error:', e)
            continue
    return jobs


def add_new_jobs():
    """当日新岗注入入口 (无需改本源码)。

    优先读取 new_jobs_draft.json (由 Stage 1 发现 + 逐条核实后生成), 存在则自动合并;
    不存在则返回 [] —— 页面仍会正常剔除过期岗位 + 重排旧岗 + 部署, 只是没有当日新公告。

    草稿 JSON 格式 (list[dict], 字段均可选):
      {"school","position","region","city","edu","hire","count",
       "salary","deadline","url","position_type","tags"}
      deadline: "YYYY-MM-DD" | "X月X日截止" | "长期"/"招满即止" | "2099-12-31"
    解析失败的条目会被跳过, 不会误注入。
    """
    for dp in DRAFT_PATHS:
        if os.path.exists(dp):
            try:
                items = json.load(open(dp, encoding='utf-8'))
                jobs = []
                for d in items:
                    dl = parse_deadline(d.get('deadline', ''))
                    if dl is None:
                        continue
                    jobs.append(Job(
                        d.get('school', ''), d.get('position', ''),
                        d.get('region') or region_of_city(d.get('city', '')),
                        d.get('edu', '本科'), d.get('hire', '劳务派遣'),
                        d.get('count', '若干'), d.get('salary', '面议'),
                        dl, d.get('city', ''), d.get('url', ''),
                        d.get('position_type', '行政管理'),
                        d.get('tags', []), is_new=True))
                print(f'add_new_jobs: loaded {len(jobs)} from {dp}')
                return jobs
            except Exception as e:
                print('add_new_jobs draft error:', e)
    return []


def dedupe_jobs(jobs):
    seen = set()
    out = []
    for j in jobs:
        key = (j.school, j.position, j.city)
        if key in seen:
            continue
        norm_pos = re.sub(r'[（(][^）)]+[）)]', '', j.position)
        norm_pos = re.sub(r'\d{4}年\d{1,2}月|\d+名|招聘启事|公告|招聘', '', norm_pos).strip()
        dup_key = (j.school, norm_pos, j.city)
        if dup_key in seen:
            continue
        seen.add(key)
        seen.add(dup_key)
        out.append(j)
    return out


def sort_jobs(jobs):
    return sorted(jobs, key=lambda j: (0 if is_tier1(j.city) else 1,
                                        j.deadline, REGION_PRIORITY.get(j.region, 99), j.school))


def render_card(job, is_new=False):
    esc_school = escape(job.school)
    esc_position = escape(job.position)
    esc_city = escape(job.city)
    dl_text = job.deadline_text()
    dl_class, dl_icon = deadline_css(job.deadline)
    badge_class = job.badge_class()
    tags_html = ''.join(f'<span class="tag tag-public">{escape(t)}</span>' for t in job.tags)
    new_badge = '<div class="new-badge">NEW</div>' if is_new else ''
    return f'''            <div class="job-card" data-region="{job.region}" data-education="{job.education}" data-hire="{job.hire_type}" data-hire-type="{job.hire_type}" data-position="{job.position_type}" style="cursor:pointer" onclick="window.open('{job.url}','_blank')">
                {new_badge}<div class="card-header">
                    <div>
                        <div class="school-name">{esc_school}</div>
                        <div class="school-tags">
                            {tags_html}
                        </div>
                    </div>
                    <span class="hire-type-badge {badge_class}">{job.hire_type}</span>
                </div>
                <div class="card-body">
                    <div class="position-name">{esc_position}</div>
                    <div class="info-grid">
                        <div class="info-item"><i class="fas fa-users"></i> <span class="value">{job.headcount}</span></div>
                        <div class="info-item"><i class="fas fa-graduation-cap"></i> <span class="value">{job.education}及以上</span></div>
                        <div class="info-item"><i class="fas fa-yen-sign"></i> <span class="value">{escape(job.salary)}</span></div>
                        <div class="info-item"><i class="fas fa-building"></i> <span class="value">{esc_city}</span></div>
                    </div>
                </div>
                <div class="card-footer">
                    <div class="deadline {dl_class}"><i class="fas {dl_icon}"></i> {dl_text}</div>
                    <a href="{job.url}" target="_blank" class="apply-link" onclick="event.stopPropagation()">查看详情</a>
                </div>
            </div>
'''


def render_cards(jobs):
    return '\n'.join(render_card(j, getattr(j, 'is_new', False)) for j in jobs)


def update_html(html, jobs):
    n = len(jobs)
    urgent = sum(1 for j in jobs if j.deadline.year != 2099 and (j.deadline - TODAY).days <= 3)
    html = re.sub(r'<title>.*?</title>', f'<title>高校行政岗招聘信息 - {PAGE_DATE}</title>', html)
    html = re.sub(r'<div class="update-time"[^>]*>.*?</div>',
                  f'<div class="update-time">更新时间：{TODAY.year}年{TODAY.month}月{TODAY.day}日</div>', html)
    html = re.sub(r'<span class="stat-num" id="totalCount"[^>]*>\d+</span>',
                  f'<span class="stat-num" id="totalCount">{n}</span>', html)
    html = re.sub(r'<span class="stat-num" id="newCount"[^>]*>\d+</span>',
                  f'<span class="stat-num" id="newCount">{sum(1 for j in jobs if getattr(j,"is_new",False))}</span>', html)
    html = re.sub(r'<span class="stat-num" id="urgentCount"[^>]*>\d+</span>',
                  f'<span class="stat-num" id="urgentCount">{urgent}</span>', html)
    html = re.sub(r'<span id="filteredCount"[^>]*>\d+</span>',
                  f'<span id="filteredCount">{n}</span>', html)
    html = re.sub(r"(const PAGE_DATE = ')[\d\-]+(';)", f"\\g<1>{PAGE_DATE}\\g<2>", html)
    # 日期选择器 input 的 value/max 属性跟随本页数据日期（否则显示旧日期）
    html = re.sub(r'(<input type="date" id="datePicker"[^>]*?value=")[\d\-]+(")',
                  f'\\g<1>{PAGE_DATE}\\g<2>', html)
    html = re.sub(r'(<input type="date" id="datePicker"[^>]*?max=")[\d\-]+(")',
                  f'\\g<1>{PAGE_DATE}\\g<2>', html)
    start = html.find('<div class="cards-grid" id="cardsGrid"')
    if start == -1:
        raise ValueError('cards-grid not found')
    start = html.find('>', start) + 1
    end_marker = html.find('<!-- 无结果提示 -->')
    if end_marker == -1:
        raise ValueError('no-results marker not found')
    end = html.rfind('</div>', 0, end_marker)
    if end == -1:
        raise ValueError('cards-grid end not found')
    html = html[:start] + '\n' + render_cards(jobs) + '\n        ' + html[end:]
    return html


def main():
    old_path = os.path.join(BASE_DIR, 'index.html')
    html = open(old_path, 'r', encoding='utf-8').read()
    old_jobs = extract_jobs_from_html(html)
    print(f'Extracted {len(old_jobs)} jobs from old page')
    kept = [j for j in old_jobs if j.deadline > TODAY]
    removed = [j for j in old_jobs if j.deadline <= TODAY]
    print(f'Kept {len(kept)} jobs, removed {len(removed)} jobs')

    new_jobs = [j for j in add_new_jobs() if j.deadline > TODAY]
    print(f'Added {len(new_jobs)} new jobs from search')

    all_jobs = sort_jobs(dedupe_jobs(new_jobs + kept))
    print(f'Total after dedupe and sort: {len(all_jobs)}')

    def norm(s):
        s = re.sub(r'[（(][^）)]+[）)]', '', s)
        return re.sub(r'\d{4}年\d{1,2}月|\d+名|招聘启事|公告|招聘', '', s).strip()
    old_norm_keys = {(j.school, norm(j.position), j.city) for j in old_jobs}
    for j in all_jobs:
        if (j.school, norm(j.position), j.city) not in old_norm_keys:
            j.is_new = True

    new_html = update_html(html, all_jobs)
    open(old_path, 'w', encoding='utf-8').write(new_html)
    print(f'Wrote {old_path}')

    archive_dir = os.path.join(BASE_DIR, 'archive')
    os.makedirs(archive_dir, exist_ok=True)
    archive_path = os.path.join(archive_dir, PAGE_DATE + '.html')
    open(archive_path, 'w', encoding='utf-8').write(new_html)
    print(f'Wrote {archive_path}')

    stats = {'total': len(all_jobs),
             'new': sum(1 for j in all_jobs if j.is_new),
             'urgent': sum(1 for j in all_jobs if j.deadline.year != 2099 and (j.deadline - TODAY).days <= 3),
             'removed': len(removed), 'kept': len(kept)}
    json.dump(stats, open(os.path.join(BASE_DIR, 'stats_' + PAGE_DATE + '.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    print('Stats:', stats)


if __name__ == '__main__':
    main()
