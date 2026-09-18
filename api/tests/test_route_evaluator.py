from django.test import TestCase
from unittest.mock import patch
from api.services.route_evaluator_service import RouteEvaluatorService

class RouteEvaluatorServiceTests(TestCase):
    @patch('api.services.route_evaluator_service.OptimizationService.calculate_optimal_stops')
    @patch('api.services.route_evaluator_service.SpatialService.filter_and_project_stations')
    @patch('api.services.route_evaluator_service.StationRepository.get_all_stations')
    def test_evaluate_candidates_selects_lowest_cost(self, mock_get_stations, mock_filter, mock_optimize):
        mock_get_stations.return_value = []
        mock_filter.return_value = []
        
        # We have 3 routes
        candidates = [
            {"distance_miles": 1000, "duration_minutes": 900, "geometry": {}},
            {"distance_miles": 1050, "duration_minutes": 950, "geometry": {}},
            {"distance_miles": 1100, "duration_minutes": 1000, "geometry": {}}
        ]
        
        # Optimization returns costs: 150, 100, 200
        mock_optimize.side_effect = [
            {"total_cost": 150.0, "total_purchased_gallons": 50.0, "fuel_stops": [{"mock": "stop1"}]},
            {"total_cost": 100.0, "total_purchased_gallons": 33.3, "fuel_stops": [{"mock": "stop2"}]},
            {"total_cost": 200.0, "total_purchased_gallons": 66.6, "fuel_stops": [{"mock": "stop3"}]}
        ]
        
        result = RouteEvaluatorService.evaluate_candidates(candidates)
        
        # Selected route should be index 1 because it has the lowest cost (100.0)
        self.assertEqual(result['selected_route']['route_index'], 1)
        self.assertEqual(result['selected_route']['fuel_cost'], 100.0)
        self.assertTrue(result['selected_route']['feasible'])
        self.assertEqual(len(result['route_comparison']), 3)

    @patch('api.services.route_evaluator_service.OptimizationService.calculate_optimal_stops')
    @patch('api.services.route_evaluator_service.SpatialService.filter_and_project_stations')
    @patch('api.services.route_evaluator_service.StationRepository.get_all_stations')
    def test_evaluate_candidates_tie_breakers(self, mock_get_stations, mock_filter, mock_optimize):
        mock_get_stations.return_value = []
        mock_filter.return_value = []
        
        # Two routes with same cost, index 0 is shorter distance
        candidates = [
            {"distance_miles": 1000, "duration_minutes": 900, "geometry": {}},
            {"distance_miles": 1050, "duration_minutes": 900, "geometry": {}},
        ]
        
        # Same cost
        mock_optimize.side_effect = [
            {"total_cost": 100.0, "total_purchased_gallons": 30.0, "fuel_stops": []},
            {"total_cost": 100.0, "total_purchased_gallons": 30.0, "fuel_stops": []},
        ]
        
        result = RouteEvaluatorService.evaluate_candidates(candidates)
        
        # Should pick index 0 because distance is shorter
        self.assertEqual(result['selected_route']['route_index'], 0)

    @patch('api.services.route_evaluator_service.OptimizationService.calculate_optimal_stops')
    @patch('api.services.route_evaluator_service.SpatialService.filter_and_project_stations')
    @patch('api.services.route_evaluator_service.StationRepository.get_all_stations')
    def test_evaluate_candidates_infeasible(self, mock_get_stations, mock_filter, mock_optimize):
        mock_get_stations.return_value = []
        mock_filter.return_value = []
        
        candidates = [{"distance_miles": 1000, "duration_minutes": 900, "geometry": {}}]
        
        # Optimizer raises exception for unreachable
        mock_optimize.side_effect = Exception("Unreachable")
        
        with self.assertRaises(Exception) as context:
            RouteEvaluatorService.evaluate_candidates(candidates)
            
        self.assertIn("Destination cannot be reached", str(context.exception))

    @patch('api.services.route_evaluator_service.OptimizationService.calculate_optimal_stops')
    @patch('api.services.route_evaluator_service.SpatialService.filter_and_project_stations')
    @patch('api.services.route_evaluator_service.StationRepository.get_all_stations')
    def test_evaluate_candidates_partial_infeasible(self, mock_get_stations, mock_filter, mock_optimize):
        mock_get_stations.return_value = []
        mock_filter.return_value = []
        
        candidates = [
            {"distance_miles": 1000, "duration_minutes": 900, "geometry": {}},
            {"distance_miles": 1200, "duration_minutes": 1000, "geometry": {}}
        ]
        
        # First is infeasible, second is feasible
        mock_optimize.side_effect = [
            Exception("Unreachable"),
            {"total_cost": 200.0, "total_purchased_gallons": 66.6, "fuel_stops": [{"mock": "stop"}]}
        ]
        
        result = RouteEvaluatorService.evaluate_candidates(candidates)
        
        # Should pick index 1
        self.assertEqual(result['selected_route']['route_index'], 1)
        self.assertEqual(result['route_comparison'][0]['feasible'], False)
        self.assertEqual(result['route_comparison'][1]['feasible'], True)
