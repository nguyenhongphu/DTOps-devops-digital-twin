from datetime import datetime

import pytest

from features.cockpit.cockpit import Cockpit

import unittest

from utils.neo4j import Neo4j


class IntegrationTest(unittest.TestCase):

    def test_smoke(self):
        Cockpit.construct_digital_twin(repo_url='https://github.com/jangruenwaldt/xss-escape-django',
                                       release_branch_name='master', debug_options={'enable_logs': True}, wipe_db=True)
        self.assertEqual(Neo4j.count_nodes(), 20)

        lead_time = Cockpit.calculate_dora_lead_time()
        self.assertEqual(lead_time.days, 1216)

        lead_time = Cockpit.calculate_dora_deployment_frequency()
        self.assertEqual(lead_time.days, 3)

        lead_time = Cockpit.calculate_dora_deployment_frequency(from_date=datetime(2023, 4, 12),
                                                                to_date=datetime(2023, 4, 14))
        self.assertEqual(lead_time.days, 0)

        cfr = Cockpit.calculate_dora_change_failure_rate()
        self.assertEqual(round(cfr, 2), 0.33)

        mttr = Cockpit.calculate_dora_mean_time_to_restore_service()
        self.assertEqual(mttr.total_seconds(), 152)


if __name__ == '__main__':
    unittest.main()
