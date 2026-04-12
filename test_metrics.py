import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, './lambda-package')

# Mock boto3 before importing lambda_function
mock_boto3 = MagicMock()
patch('boto3.resource', return_value=mock_boto3).start()
patch('boto3.client', return_value=mock_boto3).start()

import lambda_function

class TestMetrics(unittest.TestCase):
    @patch('lambda_function.push_metric')
    @patch('lambda_function.list_incidents')
    @patch('lambda_function.publish_incident_alert')
    @patch('lambda_function.table')
    def test_create_incident_metrics(self, mock_table, mock_publish, mock_list_incidents, mock_push_metric):
        # Mock database having 5 total incidents, 2 of which are HIGH severity
        mock_list_incidents.return_value = [
            {"severity": "HIGH", "status": "OPEN"},
            {"severity": "HIGH", "status": "OPEN"},
            {"severity": "LOW", "status": "OPEN"},
            {"severity": "MEDIUM", "status": "OPEN"},
            {"severity": "MEDIUM", "status": "OPEN"}
        ]
        
        # Override call_ai to prevent network requests
        lambda_function.call_ai = MagicMock(return_value={
            "error_type": "Mock",
            "severity": "HIGH",
            "root_cause": "Test",
            "recommended_fix": "Fix"
        })
        
        # Mock logs
        lambda_function.get_logs = MagicMock(return_value=[{"log": "test log"}])

        # Run function
        lambda_function.create_incident()

        # Assert metrics were pushed correctly
        mock_push_metric.assert_any_call("TotalIncidents", 5)
        mock_push_metric.assert_any_call("HighSeverityIncidents", 2)
        print("✅ SUCCESS: TotalIncidents and HighSeverityIncidents pushed the actual dynamic DB count (5 and 2) instead of 1!")

    @patch('lambda_function.push_metric')
    @patch('lambda_function.count_resolved_incidents')
    @patch('lambda_function.table')
    @patch('lambda_function.s3')
    def test_update_incident_metrics(self, mock_s3, mock_table, mock_count, mock_push_metric):
        # Mock 10 total resolved incidents
        mock_count.return_value = 10
        mock_table.update_item.return_value = {"Attributes": {"status": "RESOLVED"}}
        
        # Run function
        lambda_function.update_incident({"incident_id": "123", "status": "RESOLVED"})
        
        mock_push_metric.assert_any_call("ResolvedIncidents", 10)
        print("✅ SUCCESS: ResolvedIncidents pushed the dynamic count (10) instead of 1!")

if __name__ == '__main__':
    unittest.main(verbosity=0)
