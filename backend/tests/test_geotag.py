import unittest

from app.ingest.geotag import classify


class ClassifierTests(unittest.TestCase):
    def test_patriot_does_not_match_riot(self):
        result = classify(
            "Patriot systems repaired at German base",
            "Suspicious drones were observed over Mechernich.",
            "AO_EUROPE",
        )
        self.assertNotEqual(result.category, "civil_unrest")
        self.assertFalse(result.is_sigact)
        self.assertEqual(result.country, "Germany")
        self.assertEqual(result.ao, "AO_EUROPE")

    def test_missile_attack_beats_interception_language(self):
        result = classify(
            "Russia attacks Ukraine with six ballistic missiles",
            "None of the missiles launched overnight were intercepted.",
            "AO_EUROPE",
        )
        self.assertEqual(result.category, "kinetic_strike")
        self.assertEqual(result.severity, 5)
        self.assertTrue(result.is_sigact)
        self.assertEqual(result.ao, "AO_EUROPE")

    def test_finland_is_high_north(self):
        result = classify(
            "GPS jamming reported over Finland",
            "Aircraft reported signal interference near Helsinki.",
            "AO_EUROPE",
        )
        self.assertEqual(result.ao, "AO_HIGH_NORTH")
        self.assertEqual(result.country, "Finland")

    def test_ukraine_is_separate_from_high_north(self):
        result = classify(
            "Drone strike reported in Ukraine",
            "Air defence activity was reported near Kyiv.",
            "AO_HIGH_NORTH",
        )
        self.assertEqual(result.ao, "AO_EUROPE")
        self.assertEqual(result.country, "Ukraine")

    def test_whole_word_riot_still_matches(self):
        result = classify(
            "Prison riot leaves three dead in Jordan",
            "Security forces restored order.",
            "AO_LEVANT",
        )
        self.assertEqual(result.category, "civil_unrest")
        self.assertTrue(result.is_sigact)

    def test_specific_location_wins(self):
        result = classify(
            "Rocket fire reported in south Lebanon",
            "The incident took place near the border.",
            "AO_LEVANT",
        )
        self.assertEqual(result.country, "Lebanon")
        self.assertAlmostEqual(result.lat, 33.27)

    def test_background_article_is_not_sigact(self):
        result = classify(
            "New hydraulic system found near Suez",
            "Archaeologists described an ancient bath complex.",
            "AO_LEVANT",
        )
        self.assertEqual(result.category, "unclassified_reporting")
        self.assertFalse(result.is_sigact)

    def test_cyber_attack_is_classified(self):
        result = classify(
            "DDoS attack disrupts government services in Estonia",
            "Authorities reported a sustained cyber incident in Tallinn.",
            "AO_HIGH_NORTH",
        )
        self.assertEqual(result.category, "cyber_attack")
        self.assertEqual(result.country, "Estonia")
        self.assertEqual(result.ao, "AO_HIGH_NORTH")

    def test_kosovo_is_in_balkans_ao(self):
        result = classify(
            "Weapons seizure reported in Kosovo",
            "Police recovered rifles near Pristina.",
            "GLOBAL",
        )
        self.assertEqual(result.category, "security_operation")
        self.assertEqual(result.country, "Kosovo")
        self.assertEqual(result.ao, "AO_BALKANS")

    def test_serbia_is_separate_from_ukraine_and_eastern_europe(self):
        result = classify(
            "Military exercise begins in Serbia",
            "Units deployed near Belgrade for the exercise.",
            "AO_EUROPE",
        )
        self.assertEqual(result.country, "Serbia")
        self.assertEqual(result.ao, "AO_BALKANS")


if __name__ == "__main__":
    unittest.main()
