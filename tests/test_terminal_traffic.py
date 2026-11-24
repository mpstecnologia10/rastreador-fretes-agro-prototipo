import unittest
from datetime import datetime,timezone
from pipeline.traffic import snapshot


class TrafficTests(unittest.TestCase):
    def test_absence_is_not_normal(self):
        rows=snapshot()["terminais"]
        self.assertEqual(len(rows),3)
        self.assertTrue(all(r["jam_level"] is None for r in rows))

    def test_radius_time_and_segment_crossing(self):
        now=datetime(2026,11,24,tzinfo=timezone.utc)
        base=snapshot()["terminais"][0]
        x,y=base["lon"],base["lat"]
        jam={"level":2,"pubMillis":now.timestamp()*1000,
             "line":[{"x":x-.04,"y":y},{"x":x+.04,"y":y}]}
        result=snapshot({"jams":[jam,dict(jam,level=5,pubMillis=(now.timestamp()-901)*1000),
            dict(jam,level=3,pubMillis=(now.timestamp()+1)*1000),
            dict(jam,level=4,line=[{"x":x,"y":y+.04}])]},now)["terminais"]
        self.assertEqual([r["jam_level"] for r in result],[2,None,None])
