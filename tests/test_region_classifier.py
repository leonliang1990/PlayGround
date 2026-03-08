from core.classify.region_classifier import RegionClassifier
from core.models import FollowRecord


def test_infer_region_from_bio():
    classifier = RegionClassifier()
    record = FollowRecord(username="sample", bio="UX designer based in Seoul")
    assert classifier.infer_for_record(record) == "korea"


def test_infer_region_from_city_keyword():
    classifier = RegionClassifier()
    record = FollowRecord(username="sample", bio="Motion designer in Milan")
    assert classifier.infer_for_record(record) == "italy"
