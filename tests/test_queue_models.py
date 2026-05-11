import math
import unittest

from queue_models import mgc, mgck, mm1, mmc, mmck


class QueueModelTests(unittest.TestCase):
    def test_mm1_stable_metrics(self):
        result = mm1(2, 3)

        self.assertTrue(result["stable"])
        self.assertAlmostEqual(result["rho"], 2 / 3)
        self.assertAlmostEqual(result["L"], 2.0)
        self.assertAlmostEqual(result["Lq"], 4 / 3)
        self.assertAlmostEqual(result["W"], 1.0)
        self.assertAlmostEqual(result["Wq"], 2 / 3)

    def test_mm1_unstable_is_flagged(self):
        result = mm1(3, 3)

        self.assertFalse(result["stable"])
        self.assertIn("Unstable", result["error"])

    def test_mmc_stable_metrics(self):
        result = mmc(5, 3, 2)

        self.assertTrue(result["stable"])
        self.assertAlmostEqual(result["rho"], 5 / 6)
        self.assertTrue(math.isfinite(result["Lq"]))
        self.assertTrue(math.isfinite(result["Wq"]))

    def test_mgc_matches_mmc_for_exponential_service_variance(self):
        lambda_ = 5
        mu = 2
        c = 3
        exponential_service_variance = 1 / (mu ** 2)

        mmc_result = mmc(lambda_, mu, c)
        mgc_result = mgc(lambda_, mu, c, exponential_service_variance)

        self.assertTrue(mgc_result["stable"])
        self.assertAlmostEqual(mgc_result["Wq"], mmc_result["Wq"])
        self.assertAlmostEqual(mgc_result["Lq"], mmc_result["Lq"])

    def test_mgc_waiting_time_increases_with_service_variance(self):
        low_variance = mgc(5, 2, 3, 0.25)
        high_variance = mgc(5, 2, 3, 0.50)

        self.assertTrue(low_variance["stable"])
        self.assertTrue(high_variance["stable"])
        self.assertGreater(high_variance["Wq"], low_variance["Wq"])

    def test_mmck_has_blocking_probability_and_effective_arrivals(self):
        result = mmck(5, 3, 2, 4)

        self.assertTrue(result["stable"])
        self.assertGreaterEqual(result["blocking_probability"], 0)
        self.assertLessEqual(result["blocking_probability"], 1)
        self.assertLess(result["effective_lambda"], 5)
        self.assertLessEqual(result["L"], 4)

    def test_mmck_rejects_capacity_below_server_count(self):
        result = mmck(5, 3, 3, 2)

        self.assertFalse(result["stable"])
        self.assertIn("K must be >= c", result["error"])

    def test_mgck_matches_mmck_for_exponential_service_variance(self):
        lambda_ = 5
        mu = 2
        c = 3
        capacity = 8
        exponential_service_variance = 1 / (mu ** 2)

        mmck_result = mmck(lambda_, mu, c, capacity)
        mgck_result = mgck(lambda_, mu, c, exponential_service_variance, capacity)

        self.assertTrue(mgck_result["stable"])
        self.assertAlmostEqual(mgck_result["Wq"], mmck_result["Wq"])
        self.assertAlmostEqual(
            mgck_result["blocking_probability"],
            mmck_result["blocking_probability"],
        )


if __name__ == "__main__":
    unittest.main()
