"""
母婴护理垂直领域词汇表

用于查询扩展（Query Expansion）：
- 当用户查询中包含领域术语时，自动补充同义词和相关术语
- 提升向量检索和重排的召回率

每个术语包含：
    - definition: 术语定义
    - synonyms: 同义词列表（用于查询扩展）
    - related_terms: 相关术语列表
"""
from typing import Dict, List


# ------------------------------------------------------------------ #
# 母婴护理领域术语表（30+ 核心术语）
# ------------------------------------------------------------------ #
MATERNAL_GLOSSARY: Dict[str, Dict[str, List[str]]] = {
    # ===== 黄疸与新生儿疾病 =====
    "黄疸": {
        "definition": "新生儿皮肤、巩膜发黄的症状，因胆红素蓄积所致，分生理性和病理性两种",
        "synonyms": ["新生儿黄疸", "高胆红素血症", "皮肤发黄"],
        "related_terms": ["生理性黄疸", "病理性黄疸", "胆红素", "光疗"],
    },
    "生理性黄疸": {
        "definition": "新生儿出生后2-3天出现的暂时性黄疸，因胆红素代谢特点所致，通常7-14天自行消退",
        "synonyms": ["新生儿生理性黄疸", "母乳性黄疸", "生理性高胆红素血症"],
        "related_terms": ["病理性黄疸", "胆红素", "光疗", "新生儿黄疸"],
    },
    "病理性黄疸": {
        "definition": "新生儿出生后24小时内出现或黄疸持续不退、进行性加重，需医疗干预",
        "synonyms": ["新生儿病理性黄疸", "病理性高胆红素血症"],
        "related_terms": ["生理性黄疸", "胆红素", "光疗", "换血疗法"],
    },
    "光疗": {
        "definition": "通过蓝光照射使胆红素氧化分解为水溶性异构体，经胆汁和尿液排出，治疗新生儿黄疸",
        "synonyms": ["蓝光治疗", "蓝光照射", "光照疗法", "蓝光光疗"],
        "related_terms": ["胆红素", "黄疸", "生理性黄疸", "病理性黄疸"],
    },
    "胆红素": {
        "definition": "血红蛋白代谢产物，新生儿期因肝脏代谢能力不足易蓄积导致黄疸",
        "synonyms": ["血清胆红素", "总胆红素", "直接胆红素", "间接胆红素"],
        "related_terms": ["黄疸", "光疗", "新生儿", "胆红素脑病"],
    },

    # ===== 喂养相关 =====
    "母乳喂养": {
        "definition": "用母亲乳汁喂养婴儿的方式，是世界卫生组织推荐的最佳喂养方式",
        "synonyms": ["母乳哺养", "母乳喂哺", "纯母乳喂养"],
        "related_terms": ["初乳", "配方奶", "断奶", "转奶", "溢奶"],
    },
    "配方奶": {
        "definition": "以牛乳或其他动植物蛋白为基础，模拟母乳营养成分配制的婴儿食品",
        "synonyms": ["婴儿配方奶粉", "奶粉", "配方奶粉", "代乳品"],
        "related_terms": ["母乳喂养", "辅食添加", "转奶", "奶量"],
    },
    "初乳": {
        "definition": "产后2-3天内母亲分泌的淡黄色乳汁，富含抗体和免疫因子，营养密度极高",
        "synonyms": ["产前乳", "第一口奶", "黄金奶"],
        "related_terms": ["母乳喂养", "成熟乳", "初乳喂养", "免疫球蛋白"],
    },
    "辅食添加": {
        "definition": "婴儿满6月龄后，在继续乳类喂养基础上逐步添加各类半固体/固体食物",
        "synonyms": ["添加辅食", "辅食引入", "辅食添加期", "断奶过渡期"],
        "related_terms": ["米粉", "蛋黄", "果泥", "菜泥", "辅食过敏"],
    },
    "断奶": {
        "definition": "逐步停止母乳喂养，过渡到完全由其他食物供给营养的过程",
        "synonyms": ["断母乳", "戒奶", "离乳"],
        "related_terms": ["转奶", "辅食添加", "配方奶", "断奶期"],
    },
    "转奶": {
        "definition": "从一种配方奶转换为另一种（如1段转2段、不同品牌转换）的过渡过程",
        "synonyms": ["换奶", "奶品转换", "阶段转换"],
        "related_terms": ["配方奶", "断奶", "腹泻", "转奶不适"],
    },
    "溢奶": {
        "definition": "婴儿喂奶后少量乳汁从口角流出，因胃呈水平位、贲门括约肌松弛所致",
        "synonyms": ["漾奶", "回奶", "吐奶"],
        "related_terms": ["呛奶", "拍嗝", "胃食管反流", "喂奶姿势"],
    },
    "呛奶": {
        "definition": "婴儿吃奶时乳汁误入气管引起的呛咳，严重时可导致窒息",
        "synonyms": ["呛奶窒息", "奶液呛入气管"],
        "related_terms": ["溢奶", "拍嗝", "喂奶姿势", "海姆立克"],
    },
    "拍嗝": {
        "definition": "喂奶后轻拍婴儿背部帮助排出胃内空气，减少溢奶和肠胀气",
        "synonyms": ["拍奶嗝", "打嗝", "排气"],
        "related_terms": ["溢奶", "呛奶", "喂奶姿势", "肠绞痛"],
    },

    # ===== 新生儿护理 =====
    "胎便": {
        "definition": "新生儿出生后首次排出的墨绿色黏稠大便，由胆汁、肠道分泌物等组成",
        "synonyms": ["胎粪", "初便", "新生儿胎便"],
        "related_terms": ["大便", "母乳喂养", "黄疸", "胎便排出延迟"],
    },
    "囟门": {
        "definition": "婴幼儿颅骨结合不紧形成的颅骨间隙，分前囟和后囟，是反映宝宝健康的重要窗口",
        "synonyms": ["天灵盖", "前囟门", "后囟门"],
        "related_terms": ["颅骨", "佝偻病", "脱水", "囟门凹陷", "囟门隆起"],
    },
    "红臀": {
        "definition": "俗称红屁股，因尿布更换不及时、尿液粪便刺激导致的臀部皮肤炎症",
        "synonyms": ["尿布疹", "红屁股", "尿布皮炎"],
        "related_terms": ["尿布", "护臀膏", "皮肤护理", "湿疹"],
    },
    "湿疹": {
        "definition": "婴儿常见的过敏性皮肤炎症，表现为皮肤红斑、丘疹、瘙痒，多见于面颊和头皮",
        "synonyms": ["奶癣", "特应性皮炎", "婴儿湿疹"],
        "related_terms": ["过敏", "保湿", "皮肤护理", "红臀"],
    },
    "肠绞痛": {
        "definition": "3周-3月龄婴儿常见的长时间哭闹现象，每天哭闹超过3小时、每周超过3天",
        "synonyms": ["婴儿肠绞痛", "黄昏闹", "黄昏哭"],
        "related_terms": ["拍嗝", "益生菌", "西甲硅油", "哭闹"],
    },

    # ===== 生长发育与营养 =====
    "维生素D": {
        "definition": "促进钙吸收的脂溶性维生素，新生儿出生后数天需每日补充400IU预防佝偻病",
        "synonyms": ["维D", "维生素D3", "鱼肝油", "VD"],
        "related_terms": ["钙", "佝偻病", "晒太阳", "伊可新"],
    },
    "铁剂": {
        "definition": "用于预防和治疗缺铁性贫血的口服铁制剂，通常4-6月龄后开始补充",
        "synonyms": ["补铁", "铁补充剂", "口服铁剂"],
        "related_terms": ["贫血", "辅食添加", "血红蛋白", "补铁"],
    },
    "钙": {
        "definition": "人体必需矿物质，婴儿期摄入不足可导致佝偻病、出牙延迟等",
        "synonyms": ["钙质", "补钙", "钙剂"],
        "related_terms": ["维生素D", "佝偻病", "骨骼发育", "出牙"],
    },
    "益生菌": {
        "definition": "摄入对宿主有益的活性微生物，可调节肠道菌群，改善腹泻、便秘、肠绞痛",
        "synonyms": ["肠道益生菌", "有益菌", "益生菌制剂"],
        "related_terms": ["肠绞痛", "腹泻", "便秘", "肠道菌群"],
    },

    # ===== 日常护理与保健 =====
    "疫苗接种": {
        "definition": "按照国家免疫规划程序，按时给宝宝接种各类疫苗预防传染病",
        "synonyms": ["打疫苗", "预防接种", "打预防针", "接种疫苗"],
        "related_terms": ["卡介苗", "乙肝疫苗", "脊灰疫苗", "百白破"],
    },
    "体温监测": {
        "definition": "定期测量婴儿体温，及时发现发热等异常情况，正常腋温36.0-37.3℃",
        "synonyms": ["测体温", "体温测量", "发烧监测"],
        "related_terms": ["发热", "腋温", "额温", "退热贴"],
    },
    "抚触": {
        "definition": "通过按摩婴儿皮肤和机体，促进亲子交流、改善睡眠、促进生长发育",
        "synonyms": ["婴儿抚触", "按摩", "宝宝抚触"],
        "related_terms": ["游泳", "被动操", "亲子交流", "婴儿按摩"],
    },
    "游泳": {
        "definition": "婴儿在水中进行的自主活动和抚触结合的保健运动，促进身心发育",
        "synonyms": ["婴儿游泳", "宝宝游泳", "泳疗"],
        "related_terms": ["抚触", "被动操", "水疗", "发育"],
    },
    "被动操": {
        "definition": "由家长帮助婴儿活动四肢和躯干的体操运动，促进大运动发育",
        "synonyms": ["婴儿被动操", "宝宝操", "被动体操"],
        "related_terms": ["抚触", "游泳", "大运动发育", "体格锻炼"],
    },

    # ===== 睡眠与情绪 =====
    "厌奶期": {
        "definition": "婴儿3-6月龄左右出现的奶量暂时减少、食欲下降的现象，通常持续1-2周",
        "synonyms": ["厌奶", "拒奶", "奶量下降"],
        "related_terms": ["猛长期", "转奶", "食欲", "生长发育"],
    },
    "猛长期": {
        "definition": "婴儿出生后数周和数月出现的快速生长期，表现为奶量骤增、频繁觅食、易怒",
        "synonyms": ["快速生长期", "猛涨期", "生长突增期"],
        "related_terms": ["厌奶期", "奶量", "喂养", "体重增长"],
    },
    "睡眠倒退": {
        "definition": "婴儿原本良好的睡眠模式突然变差，频繁夜醒、入睡困难，多与大运动发育相关",
        "synonyms": ["睡眠倒退期", "夜醒频繁", "睡眠紊乱"],
        "related_terms": ["睡眠训练", "夜醒", "大运动发育", "作息"],
    },
}


# ------------------------------------------------------------------ #
# 查询扩展函数
# ------------------------------------------------------------------ #
def expand_query(question: str) -> str:
    """
    根据母婴护理词汇表对用户查询进行同义词扩展。

    策略：
    1. 遍历词汇表中的每个术语，检查问题中是否包含该术语或其同义词
    2. 若命中，将该术语的同义词和相关术语追加到原查询后
    3. 扩展后的查询用于 embedding 和 reranker，提升召回率

    参数:
        question: 用户原始问题

    返回:
        扩展后的查询字符串（原问题 + 命中术语的同义词/相关术语）
    """
    if not question:
        return question

    expanded_terms: List[str] = []

    for term, info in MATERNAL_GLOSSARY.items():
        # 检查主术语是否在问题中
        if term in question:
            # 添加同义词
            for syn in info.get("synonyms", []):
                if syn not in question and syn not in expanded_terms:
                    expanded_terms.append(syn)
            # 添加相关术语
            for rel in info.get("related_terms", []):
                if rel not in question and rel not in expanded_terms:
                    expanded_terms.append(rel)
            continue

        # 检查同义词是否在问题中
        for syn in info.get("synonyms", []):
            if syn in question:
                # 添加主术语和其他同义词
                if term not in question and term not in expanded_terms:
                    expanded_terms.append(term)
                for other_syn in info.get("synonyms", []):
                    if other_syn != syn and other_syn not in question and other_syn not in expanded_terms:
                        expanded_terms.append(other_syn)
                # 添加相关术语
                for rel in info.get("related_terms", []):
                    if rel not in question and rel not in expanded_terms:
                        expanded_terms.append(rel)
                break

    if expanded_terms:
        # 拼接：原问题 + 空格 + 扩展术语（空格分隔）
        expanded_query = question + " " + " ".join(expanded_terms)
        return expanded_query

    return question


def get_glossary_terms() -> List[str]:
    """返回词汇表中所有术语列表。"""
    return list(MATERNAL_GLOSSARY.keys())
