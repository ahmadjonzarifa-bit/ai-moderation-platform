import unittest
from app.filters.regex_filter import check_text_regex

class TestRegexFilter(unittest.TestCase):

    def test_clean_text_passes(self):
        clean_samples = [
            "Отличный сервис, спасибо большое за быструю доставку!",
            "Juda yaxshi xizmat ko'rsatishdi, rahmat!",
            "Great support and high quality product.",
            "Заказ был оформлен в 2026 году, все отлично."
        ]
        for sample in clean_samples:
            is_valid, reason, vtype, _ = check_text_regex(sample)
            self.assertTrue(is_valid, f"Должен быть валидным: '{sample}', но отклонен: {reason}")

    def test_links_and_domains_blocked(self):
        link_samples = [
            "Заходи сюда https://example.com/promo",
            "Мой канал в телеграм t.me/mychannel",
            "Переходи bit.ly/3xyz",
            "Сайт магазин.uz супер скидки",
            "Заходи на google.ru прямо сейчас",
            "Смотри t . m e / mychat",
            "Пиши на сайт test точка ком"
        ]
        for sample in link_samples:
            is_valid, reason, vtype, matched = check_text_regex(sample)
            self.assertFalse(is_valid, f"Ссылка должна быть заблокирована: '{sample}'")
            self.assertEqual(vtype, "LINKS")

    def test_bank_cards_blocked(self):
        card_samples = [
            "Переведи на карту 8600 1234 5678 9012",
            "Моя карта 9860123456789012 отправь туда",
            "Оплата на 4111-2222-3333-4444"
        ]
        for sample in card_samples:
            is_valid, reason, vtype, _ = check_text_regex(sample)
            self.assertFalse(is_valid, f"Карта должна быть заблокирована: '{sample}'")
            self.assertEqual(vtype, "BANK_CARD")

    def test_phones_blocked(self):
        phone_samples = [
            "Звоните мне +998 90 123 45 67",
            "Мой номер: +79991234567",
            "Позвони 89261234567"
        ]
        for sample in phone_samples:
            is_valid, reason, vtype, _ = check_text_regex(sample)
            self.assertFalse(is_valid, f"Телефон должен быть заблокирован: '{sample}'")
            self.assertEqual(vtype, "PHONE")

    def test_usernames_and_emails_blocked(self):
        contact_samples = [
            ("Пиши мне в телегу @cryptoboss", "USERNAME"),
            ("Моя почта test@gmail.com жду", "EMAIL")
        ]
        for sample, expected_type in contact_samples:
            is_valid, reason, vtype, _ = check_text_regex(sample)
            self.assertFalse(is_valid, f"Контакт должен быть заблокирован: '{sample}'")
            self.assertEqual(vtype, expected_type)

    def test_stopwords_blocked(self):
        bad_samples = [
            "Ты полный мудак и тварь",
            "What the fuck is this",
            "Bu xizmat haromi va jalab"
        ]
        for sample in bad_samples:
            is_valid, reason, vtype, _ = check_text_regex(sample)
            self.assertFalse(is_valid, f"Мат должен быть заблокирован: '{sample}'")
            self.assertEqual(vtype, "PROFANITY")

if __name__ == "__main__":
    unittest.main()
