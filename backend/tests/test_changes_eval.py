from scripts.evaluate_changes import score


def test_mocked_reviews_flag_duplicates_unknown_citations_and_misses():
    case = {
        "evidence": [{"id": 10}, {"id": 20}],
        "reference_developments": [{"id": "a", "supporting_ids": [10]}, {"id": "b", "supporting_ids": [20]}],
    }
    mock = {"developments": [
        {"reference_id": "a", "article_ids": [10], "claims_supported": True},
        {"reference_id": "a", "article_ids": [10], "claims_supported": True},
        {"reference_id": "b", "article_ids": [20, 99], "claims_supported": True},
    ], "prose_score": 3}
    assert score(case, mock) == {
        "reference_developments_found": 1, "reference_developments_missed": ["b"],
        "supported_items": 2, "submitted_items": 3, "duplicate_items": 1,
        "unknown_citations": 1, "prose_score": 3,
    }


def test_quiet_case_does_not_reward_an_invented_development():
    result = score({"evidence": [], "reference_developments": []}, {
        "developments": [{"article_ids": [], "claims_supported": False}],
    })
    assert result["submitted_items"] == 1 and result["supported_items"] == 0
