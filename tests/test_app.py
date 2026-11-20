import unittest
from app import create_app
from app.extensions import db
from app.models import Block, Floor, Room, Equipment

class AppTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "WTF_CSRF_ENABLED": False})
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_campus_seed_counts(self):
        self.assertEqual(Block.query.count(), 11)
        self.assertEqual(Floor.query.count(), 33)
        self.assertEqual(Room.query.count(), 330)
        self.assertEqual(Room.query.filter_by(room_type="Laboratory").count(), 55)

    def test_dashboard_and_pages(self):
        for path in ["/", "/campus", "/monitoring", "/equipment", "/insights", "/reports", "/export.csv"]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)

    def test_api_flow_and_validation(self):
        bad = self.client.post("/api/readings", json={"room_code": "bad", "energy_kwh": -2})
        self.assertEqual(bad.status_code, 400)

        good = self.client.post("/api/readings", json={"room_code": "1101", "energy_kwh": 18.5})
        self.assertEqual(good.status_code, 201)

        summary = self.client.get("/api/summary")
        self.assertEqual(summary.status_code, 200)
        self.assertIn("forecast_7_days", summary.get_json())

if __name__ == "__main__":
    unittest.main()
