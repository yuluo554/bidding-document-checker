"""知识库检索（M4）：纯 Python TF 余弦 top_k、确定性排序、不引向量库。"""
from bidchecker.knowledge import load_blocks
from bidchecker.knowledge.search import search, tokenize


def test_tokenize_latin_and_cjk_bigrams():
    tokens = tokenize("ISO9001质量管理体系 认证")
    assert "iso9001" in tokens
    assert "质量" in tokens and "量管" in tokens and "理体" in tokens
    assert "认证" in tokens
    assert tokenize("") == []


def test_search_bond_query_top_hit_mentions_bond():
    results = search("投标保证金 不退还", top_k=3)
    assert len(results) == 3
    top_score, top_block = results[0]
    assert "保证金" in top_block["text"]
    assert 0.0 < top_score <= 1.0


def test_search_collusion_query_hits_collusion_articles():
    results = search("视为串通投标 投标文件异常一致", top_k=5)
    top_law_article = {(b["law"], b["article_no"]) for _, b in results[:2]}
    candidates = {("政府采购货物和服务招标投标管理办法", "第三十七条"),
                  ("招标投标法实施条例", "第三十九条"),
                  ("招标投标法实施条例", "第四十条")}
    assert top_law_article & candidates


def test_search_scores_sorted_desc_and_deterministic():
    r1 = search("评标委员会 否决投标", top_k=5)
    r2 = search("评标委员会 否决投标", top_k=5)
    scores = [s for s, _ in r1]
    assert scores == sorted(scores, reverse=True)
    assert r1 == r2  # 同查询结果逐项一致（含顺序）


def test_search_tie_break_by_law_then_article():
    """同分并列按 (law, article_no) 升序——确定性不依赖哈希序/迭代序。"""
    blocks = [
        {"law": "乙法", "article_no": "第二条", "text": "完全相同的条文文本",
         "source_url": "https://example.com", "status": "已核对"},
        {"law": "乙法", "article_no": "第一条", "text": "完全相同的条文文本",
         "source_url": "https://example.com", "status": "已核对"},
        {"law": "甲法", "article_no": "第十条", "text": "完全相同的条文文本",
         "source_url": "https://example.com", "status": "已核对"},
    ]
    results = search("完全相同", top_k=3, blocks=blocks)
    scores = [s for s, _ in results]
    assert scores == sorted(scores, reverse=True)
    keys = [(b["law"], b["article_no"]) for _, b in results]
    assert keys == [("乙法", "第一条"), ("乙法", "第二条"), ("甲法", "第十条")]


def test_search_top_k_respected_and_empty_query():
    blocks = load_blocks()
    assert len(search("投标", top_k=3, blocks=blocks)) == 3
    empty = search("", top_k=4, blocks=blocks)
    assert len(empty) == 4 and all(s == 0.0 for s, _ in empty)


def test_search_accepts_external_blocks_list():
    fake = [{"law": "测试条例", "article_no": "第一条",
             "text": "投标保证金应当在中标通知书发出后五日内退还投标人。",
             "source_url": "https://example.com", "status": "已核对"}]
    results = search("保证金 退还", blocks=fake, top_k=1)
    assert results and results[0][1]["law"] == "测试条例"
    assert results[0][0] > 0.0
