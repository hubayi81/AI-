"""reply_parser.parse_reply 纯函数单测（LLM 回复 → 结构化推荐/追问）。"""
import pytest

from reply_parser import parse_reply


def test_fenced_json_recommend():
    raw = '好的，这是推荐：\n```json\n{"recommendations": [{"productId": 1}]}\n```'
    _, action, results, _ = parse_reply(raw)
    assert action == "recommend"
    assert results == [{"productId": 1}]


def test_compare_action_keyword():
    raw = '```json\n{"recommendations": [{"productId": 1}, {"productId": 2}], "compare": true}\n```'
    _, action, results, _ = parse_reply(raw)
    assert action == "compare"
    assert len(results) == 2


def test_outfit_action_keyword():
    raw = '穿搭建议：\n```json\n{"recommendations": [{"productId": 3}], "outfit": true}\n```'
    _, action, _, _ = parse_reply(raw)
    assert action == "outfit"


def test_plain_text_falls_back_to_chat():
    raw = "抱歉我没有听懂你的问题"
    reply, action, results, follow_ups = parse_reply(raw)
    assert action == "chat"
    assert results is None
    assert reply == raw


def test_productid_substring_requires_recommendations_wrapper():
    # 仅有裸 productId、没有 recommendations 包裹时，解析器不臆造推荐，
    # 优雅降级为 chat（避免把非结构化片段当成正经推荐结果）
    raw = '这里有一双：{"productId": 7, "name": "Cloudmonster"} 你看可以吗'
    reply, action, results, _ = parse_reply(raw)
    assert action == "chat"
    assert results is None
    assert "Cloudmonster" in reply


def test_productid_inside_recommendations():
    raw = '```json\n{"recommendations": [{"productId": 7, "name": "Cloudmonster"}]}\n```'
    _, action, results, _ = parse_reply(raw)
    assert action == "recommend"
    assert results[0]["productId"] == 7


def test_broken_json_falls_back():
    raw = '```json\n{not valid json\n```'
    _, action, results, _ = parse_reply(raw)
    assert action == "chat"
    assert results is None


def test_followups_truncated_to_three():
    raw = ('```json\n'
           '{"recommendations": [{"productId": 1}], '
           '"followUps": ["a", "b", "c", "d", "e"]}\n```')
    _, _, _, follow_ups = parse_reply(raw)
    assert follow_ups is not None and len(follow_ups) == 3


def test_followups_absent_is_none():
    raw = '```json\n{"recommendations": [{"productId": 1}]}\n```'
    _, _, _, follow_ups = parse_reply(raw)
    assert follow_ups is None
