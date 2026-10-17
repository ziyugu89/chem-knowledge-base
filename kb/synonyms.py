from __future__ import annotations

# 查询扩展：把口语/英文/别称映射到教材中的标准说法
SYNONYMS: dict[str, list[str]] = {
    "氢氟酸": ["HF", "氟化氢", "无水氟化氢", "AHF", "BHF", "氢氟酸生产"],
    "氟化氢": ["HF", "氢氟酸", "无水氟化氢", "AHF"],
    "无水氟化氢": ["AHF", "HF", "氢氟酸"],
    "萤石": ["氟石", "氟化钙", "CaF2", "酸级萤石", "冶金级萤石"],
    "氟化钙": ["CaF2", "萤石", "氟石"],
    "冰晶石": ["氟铝酸钠", "Na3AlF6", "铝用氟化盐"],
    "氟化铝": ["AlF3", "铝用氟化盐"],
    "元素氟": ["氟气", "F2", "电解制氟"],
    "六氟化硫": ["SF6", "含氟特种气体"],
    "ODS": ["消耗臭氧层物质", "氟利昂", "CFC", "氟氯烃"],
    "氟利昂": ["CFC", "ODS", "氟氯烃", "CFCs"],
    "HCFC": ["氢氟氯烃", "HCFC-22", "R22", "ODS替代"],
    "HFC": ["氢氟烃", "氢氟烃替代品", "R134a", "R32", "R125"],
    "含氟医药": ["含氟药物", "氟喹诺酮", "伪拟效应", "阻断效应"],
    "含氟农药": ["含氟除草剂", "含氟杀虫剂", "含氟杀菌剂"],
    "含氟染料": ["含氟分散染料"],
    "有机氟中间体": ["含氟中间体", "芳香族含氟中间体", "氟苯", "三氟甲苯"],
    "含氟表面活性剂": ["氟碳表面活性剂", "PFOS", "PFOA", "全氟辛酸"],
    "含氟整理剂": ["织物整理剂", "防水防油整理"],
    "聚四氟乙烯": ["PTFE", "铁氟龙", "特氟龙", "F4", "聚四氟乙烯树脂"],
    "PTFE": ["聚四氟乙烯", "特氟龙", "铁氟龙", "F4"],
    "特氟龙": ["PTFE", "聚四氟乙烯", "铁氟龙"],
    "PFA": ["全氟烷氧基树脂", "可熔性氟树脂"],
    "FEP": ["聚全氟乙丙烯", "四氟乙烯-六氟丙烯共聚物", "可熔性氟树脂"],
    "ETFE": ["乙烯-四氟乙烯共聚物"],
    "PVDF": ["聚偏氟乙烯"],
    "PCTFE": ["聚三氟氯乙烯"],
    "氟橡胶": ["FKM", "氟弹性体", "偏氟乙烯橡胶"],
    "氟涂料": ["氟碳涂料", "PVDF涂料", "FEVE"],
    "氟树脂": ["含氟聚合物", "含氟树脂", "氟塑料"],
    "含氟聚合物": ["氟树脂", "氟塑料", "氟橡胶"],
}

CUSTOM_WORDS = sorted(
    {
        "氢氟酸",
        "无水氟化氢",
        "萤石",
        "氟化钙",
        "冰晶石",
        "氟化铝",
        "元素氟",
        "六氟化硫",
        "含氟烃",
        "氟氯烃",
        "氢氟氯烃",
        "氢氟烃",
        "含氟医药",
        "含氟药物",
        "含氟农药",
        "含氟染料",
        "有机氟中间体",
        "含氟表面活性剂",
        "氟碳表面活性剂",
        "含氟整理剂",
        "聚四氟乙烯",
        "可熔性氟树脂",
        "氟橡胶",
        "氟涂料",
        "含氟聚合物",
        "氟化工",
        "电解制氟",
        "萤石法",
        "伪拟效应",
        "阻断效应",
        "ODS",
        "HCFC",
        "HFC",
        "CFC",
        "PTFE",
        "PFA",
        "FEP",
        "ETFE",
        "PVDF",
        "PCTFE",
        "PFOS",
        "PFOA",
        "AHF",
        "SF6",
    }
)


def expand_query(query: str) -> str:
    extra: list[str] = []
    for key, values in SYNONYMS.items():
        if key.lower() in query.lower() or key in query:
            extra.extend(values)
        else:
            for v in values:
                if v.lower() in query.lower() or v in query:
                    extra.append(key)
                    extra.extend([x for x in values if x != v])
                    break
    if not extra:
        return query
    seen = set()
    uniq = []
    for w in extra:
        if w not in seen and w.lower() not in query.lower():
            seen.add(w)
            uniq.append(w)
    return query + " " + " ".join(uniq[:3])
