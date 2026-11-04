import pytest

from metrics import ari, groups_to_labels, pair_counts, prf, same_partition

TRUTH = {"a.py": 0, "test_a.py": 0, "b.py": 1, "test_b.py": 1}


def test_perfect_prediction_with_different_ids():
    pred = {"a.py": 7, "test_a.py": 7, "b.py": 3, "test_b.py": 3}  # ids don't matter
    assert pair_counts(TRUTH, pred) == (2, 0, 0)
    assert prf(*pair_counts(TRUTH, pred)) == (1.0, 1.0, 1.0)
    assert ari(TRUTH, pred) == pytest.approx(1.0)
    assert same_partition(TRUTH, pred)


def test_everything_in_one_group():
    pred = {f: 0 for f in TRUTH}
    tp, fp, fn = pair_counts(TRUTH, pred)
    assert (tp, fp, fn) == (2, 4, 0)            # 6 pairs, only 2 truly together
    p, r, _ = prf(tp, fp, fn)
    assert p == pytest.approx(1 / 3) and r == 1.0
    assert ari(TRUTH, pred) == pytest.approx(0.0)


def test_one_group_per_file():
    pred = {f: i for i, f in enumerate(TRUTH)}
    assert pair_counts(TRUTH, pred) == (0, 0, 2)
    p, r, f1 = prf(*pair_counts(TRUTH, pred))
    assert (p, r, f1) == (1.0, 0.0, 0.0)


def test_grouping_by_folder_is_wrong_here():
    # source together, tests together: the classic folder mistake
    pred = {"a.py": 0, "b.py": 0, "test_a.py": 1, "test_b.py": 1}
    assert pair_counts(TRUTH, pred) == (0, 2, 2)
    assert ari(TRUTH, pred) < 0


def test_degenerate_all_singletons():
    truth = {"a": 0, "b": 1, "c": 2}
    assert ari(truth, {"a": 5, "b": 6, "c": 7}) == 1.0
    assert ari(truth, {"a": 0, "b": 0, "c": 0}) == 0.0


def test_groups_to_labels():
    groups = [{"files": ["a.py", "test_a.py"]}, {"files": ["b.py"]}]
    assert groups_to_labels(groups) == {"a.py": 0, "test_a.py": 0, "b.py": 1}
