import unittest
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import init_db

class TestApiFlow(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        await init_db()
        self.transport = ASGITransport(app=app)

    async def test_health_check(self):
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            resp = await client.get("/health")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "ok")

    async def test_regex_check_endpoint(self):
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            # Ссылка
            bad_resp = await client.post("/api/v1/messages/check-regex", json={"text": "Подпишись https://t.me/channel"})
            self.assertEqual(bad_resp.status_code, 200)
            bad_data = bad_resp.json()
            self.assertFalse(bad_data["is_valid"])

            # Чистый текст
            good_resp = await client.post("/api/v1/messages/check-regex", json={"text": "Отличный товар, мне всё понравилось"})
            self.assertEqual(good_resp.status_code, 200)
            good_data = good_resp.json()
            self.assertTrue(good_data["is_valid"])

    async def test_message_creation_and_reporting_flow(self):
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            # 1. Попытка отправить сообщение со ссылкой (должно быть отклонено 422)
            rej_resp = await client.post("/api/v1/messages", json={
                "original_text": "Переходите на сайт www.myspam.com и покупайте",
                "user_name": "Спамер",
                "type": "COMMENT"
            })
            self.assertEqual(rej_resp.status_code, 422)

            # 2. Отправка чистого сообщения (при отсутствии GEMINI_API_KEY уходит в 202 PENDING_MODERATION)
            create_resp = await client.post("/api/v1/messages", json={
                "original_text": "Отличный сервис, очень быстро привезли заказ!",
                "user_name": "Тестовый Клиент",
                "type": "REVIEW"
            })
            self.assertIn(create_resp.status_code, [201, 202])
            msg = create_resp.json()
            msg_id = msg["id"]

            # 3. Модератор одобряет сообщение через админку
            approve_resp = await client.patch(f"/api/v1/admin/messages/{msg_id}/moderate", json={
                "action": "APPROVE",
                "ban_user": False
            })
            self.assertEqual(approve_resp.status_code, 200)
            self.assertEqual(approve_resp.json()["new_status"], "PUBLISHED")

            # 4. Проверяем, что сообщение появилось в публичной ленте
            feed_resp = await client.get("/api/v1/messages")
            self.assertEqual(feed_resp.status_code, 200)
            feed = feed_resp.json()
            self.assertTrue(any(m["id"] == msg_id for m in feed))

            # 5. Пользователь отправляет жалобу на сообщение
            report_resp = await client.post(f"/api/v1/messages/{msg_id}/report", json={
                "reason": "CTA",
                "comment": "Подозрительное сообщение",
                "reporter_id": "user_42"
            })
            self.assertEqual(report_resp.status_code, 200)
            self.assertTrue(report_resp.json()["success"])

            # 6. Повторная жалоба от того же пользователя должна быть отклонена (защита от накрутки)
            dup_report_resp = await client.post(f"/api/v1/messages/{msg_id}/report", json={
                "reason": "CTA",
                "reporter_id": "user_42"
            })
            self.assertEqual(dup_report_resp.status_code, 400)

            # 7. Проверяем статистику в админке
            stats_resp = await client.get("/api/v1/admin/stats")
            self.assertEqual(stats_resp.status_code, 200)
            stats = stats_resp.json()
            self.assertGreaterEqual(stats["total_messages"], 1)
            self.assertGreaterEqual(stats["total_reports"], 1)

if __name__ == "__main__":
    unittest.main()
