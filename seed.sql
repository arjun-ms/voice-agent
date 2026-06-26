INSERT INTO users (id, phone_number, name) VALUES (1, '+1234567890', 'Test User') ON CONFLICT DO NOTHING;
INSERT INTO conversation_summaries (user_id, summary_text, appointments_json, preferences) 
VALUES (1, 'User asked about a dental checkup. Booked a slot for tomorrow.', '[{"date": "2026-06-27", "time": "10:00 AM", "status": "booked"}]', 'Prefers morning appointments.');
