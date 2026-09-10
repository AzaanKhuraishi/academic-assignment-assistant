import unittest

from assignment_assistant.routing import load_keyword_profiles, route_subject


class RoutingTests(unittest.TestCase):
    def test_profiles_are_loaded_from_packaged_overlay_data(self):
        profiles = load_keyword_profiles()
        self.assertIn("consultancy", profiles)
        self.assertEqual(profiles["cryptography"]["nonce"], 4)

    def test_explicit_override_wins(self):
        result = route_subject("client stakeholder consultancy", "humanities")
        self.assertEqual(result["discipline"], "humanities")
        self.assertEqual(result["confidence"], 1.0)

    def test_weak_signal_requires_confirmation(self):
        result = route_subject("This essay discusses a network.")
        self.assertEqual(result["discipline"], "cybersecurity")
        self.assertTrue(result["requires_confirmation"])

    def test_mixed_signal_requires_confirmation(self):
        result = route_subject(
            "A consultancy client needs a stakeholder analysis of a cryptography cipher."
        )
        self.assertTrue(result["requires_confirmation"])

    def test_no_signal_routes_to_generic(self):
        result = route_subject("Write an assessed report using the supplied material.")
        self.assertEqual(result["discipline"], "generic")
        self.assertTrue(result["requires_confirmation"])


if __name__ == "__main__":
    unittest.main()
