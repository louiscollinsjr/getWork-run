"""
Monitoring and alerting system for job collection
Tracks performance, detects issues, and sends alerts
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from supabase import create_client, Client
from config_manager import config_manager

logger = logging.getLogger(__name__)

@dataclass
class Alert:
    """Represents a system alert"""
    id: str
    type: str
    severity: str  # info, warning, error, critical
    message: str
    details: Dict[str, Any]
    created_at: datetime
    resolved: bool = False

@dataclass
class CollectionMetrics:
    """Collection performance metrics"""
    total_jobs: int
    jobs_by_site: Dict[str, int]
    success_rate: float
    error_rate: float
    avg_processing_time: float
    company_extraction_rate: float
    duplicate_rate: float
    top_search_terms: List[Dict[str, Any]]

class MonitoringSystem:
    """Monitors job collection system health and performance"""
    
    def __init__(self):
        self.config = config_manager.get_config()
        self.supabase = create_client(self.config.supabase_url, self.config.supabase_key)
        self.alerts: List[Alert] = []
    
    def collect_metrics(self, time_window_hours: int = 24) -> CollectionMetrics:
        """Collect system metrics for the specified time window"""
        try:
            since_time = datetime.now() - timedelta(hours=time_window_hours)
            
            # Get basic job statistics
            jobs_query = self.supabase.table('jobs').select('*').gte('collected_at', since_time.isoformat())
            jobs_result = jobs_query.execute()
            jobs = jobs_result.data
            
            if not jobs:
                return CollectionMetrics(
                    total_jobs=0,
                    jobs_by_site={},
                    success_rate=0.0,
                    error_rate=0.0,
                    avg_processing_time=0.0,
                    company_extraction_rate=0.0,
                    duplicate_rate=0.0,
                    top_search_terms=[]
                )
            
            # Calculate metrics
            total_jobs = len(jobs)
            
            # Jobs by site
            jobs_by_site = {}
            company_extraction_count = 0
            
            for job in jobs:
                site = job.get('source_site', 'unknown')
                jobs_by_site[site] = jobs_by_site.get(site, 0) + 1
                
                if job.get('company') and job.get('company') != 'Unknown Company':
                    company_extraction_count += 1
            
            # Calculate rates
            company_extraction_rate = company_extraction_count / total_jobs if total_jobs > 0 else 0
            
            # Get error statistics from logs or database
            error_rate = self._calculate_error_rate(since_time)
            
            # Get duplicate statistics
            duplicate_rate = self._calculate_duplicate_rate(since_time)
            
            # Get top search terms
            top_search_terms = self._get_top_search_terms(jobs)
            
            return CollectionMetrics(
                total_jobs=total_jobs,
                jobs_by_site=jobs_by_site,
                success_rate=company_extraction_rate,
                error_rate=error_rate,
                avg_processing_time=0.0,  # Would need timing data
                company_extraction_rate=company_extraction_rate,
                duplicate_rate=duplicate_rate,
                top_search_terms=top_search_terms
            )
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {str(e)}")
            raise
    
    def check_system_health(self) -> List[Alert]:
        """Check system health and generate alerts"""
        alerts = []
        metrics = self.collect_metrics(24)  # Last 24 hours
        thresholds = self.config.alert_thresholds
        
        # Check daily job collection threshold
        if metrics.total_jobs < thresholds['min_daily_jobs']:
            alerts.append(Alert(
                id=f"low_collection_{datetime.now().strftime('%Y%m%d')}",
                type="low_collection",
                severity="warning",
                message=f"Daily job collection ({metrics.total_jobs}) below threshold ({thresholds['min_daily_jobs']})",
                details={"actual": metrics.total_jobs, "threshold": thresholds['min_daily_jobs']},
                created_at=datetime.now()
            ))
        
        # Check company extraction rate
        if metrics.company_extraction_rate < (1 - thresholds['max_missing_company_rate']):
            alerts.append(Alert(
                id=f"low_company_rate_{datetime.now().strftime('%Y%m%d')}",
                type="data_quality",
                severity="error",
                message=f"Company extraction rate ({metrics.company_extraction_rate:.2%}) below acceptable level",
                details={
                    "actual_rate": metrics.company_extraction_rate,
                    "threshold": 1 - thresholds['max_missing_company_rate']
                },
                created_at=datetime.now()
            ))
        
        # Check error rate
        if metrics.error_rate > thresholds['max_error_rate']:
            alerts.append(Alert(
                id=f"high_error_rate_{datetime.now().strftime('%Y%m%d')}",
                type="high_errors",
                severity="error",
                message=f"Error rate ({metrics.error_rate:.2%}) exceeds threshold ({thresholds['max_error_rate']:.2%})",
                details={"actual_rate": metrics.error_rate, "threshold": thresholds['max_error_rate']},
                created_at=datetime.now()
            ))
        
        # Check if collection has stopped
        recent_jobs = self.supabase.table('jobs').select('collected_at').gte(
            'collected_at', 
            (datetime.now() - timedelta(hours=thresholds['max_hours_without_collection'])).isoformat()
        ).execute()
        
        if not recent_jobs.data:
            alerts.append(Alert(
                id=f"collection_stopped_{datetime.now().strftime('%Y%m%d_%H')}",
                type="collection_stopped",
                severity="critical",
                message=f"No jobs collected in the last {thresholds['max_hours_without_collection']} hours",
                details={"hours_without_collection": thresholds['max_hours_without_collection']},
                created_at=datetime.now()
            ))
        
        # Store alerts in database
        for alert in alerts:
            self._store_alert(alert)
        
        return alerts
    
    def _calculate_error_rate(self, since_time: datetime) -> float:
        """Calculate error rate based on logs or error records"""
        try:
            # This would ideally connect to your logging system
            # For now, we'll estimate based on jobs with missing data
            total_attempts_query = self.supabase.table('jobs').select('id', 'company').gte('collected_at', since_time.isoformat())
            total_attempts = total_attempts_query.execute()
            
            if not total_attempts.data:
                return 0.0
            
            error_count = sum(1 for job in total_attempts.data if not job.get('company') or job.get('company') == 'Unknown Company')
            return error_count / len(total_attempts.data)
            
        except Exception as e:
            logger.error(f"Error calculating error rate: {str(e)}")
            return 0.0
    
    def _calculate_duplicate_rate(self, since_time: datetime) -> float:
        """Calculate duplicate job rate"""
        try:
            jobs_query = self.supabase.table('jobs').select('job_url_hash').gte('collected_at', since_time.isoformat())
            jobs_result = jobs_query.execute()
            
            if not jobs_result.data:
                return 0.0
            
            total_jobs = len(jobs_result.data)
            unique_hashes = len(set(job['job_url_hash'] for job in jobs_result.data if job.get('job_url_hash')))
            
            if total_jobs == 0:
                return 0.0
            
            return (total_jobs - unique_hashes) / total_jobs
            
        except Exception as e:
            logger.error(f"Error calculating duplicate rate: {str(e)}")
            return 0.0
    
    def _get_top_search_terms(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get top performing search terms"""
        term_counts = {}
        
        for job in jobs:
            term = job.get('search_term_used')
            if term:
                term_counts[term] = term_counts.get(term, 0) + 1
        
        sorted_terms = sorted(term_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"term": term, "count": count} for term, count in sorted_terms[:10]]
    
    def _store_alert(self, alert: Alert):
        """Store alert in database"""
        try:
            alert_data = {
                'alert_type': alert.type,
                'severity': alert.severity,
                'message': alert.message,
                'metadata': alert.details,
                'created_at': alert.created_at.isoformat()
            }
            
            self.supabase.table('collection_alerts').insert(alert_data).execute()
            logger.info(f"Stored alert: {alert.type} - {alert.severity}")
            
        except Exception as e:
            logger.error(f"Error storing alert: {str(e)}")
    
    def generate_daily_report(self) -> Dict[str, Any]:
        """Generate comprehensive daily report"""
        try:
            metrics = self.collect_metrics(24)
            alerts = self.check_system_health()
            
            # Get quota usage
            quota_query = self.supabase.table('quota_tracking').select('*').gte('date', datetime.now().date().isoformat())
            quota_result = quota_query.execute()
            
            report = {
                'date': datetime.now().date().isoformat(),
                'summary': {
                    'total_jobs_collected': metrics.total_jobs,
                    'company_extraction_rate': f"{metrics.company_extraction_rate:.1%}",
                    'error_rate': f"{metrics.error_rate:.1%}",
                    'duplicate_rate': f"{metrics.duplicate_rate:.1%}",
                    'active_alerts': len([a for a in alerts if not a.resolved])
                },
                'jobs_by_site': metrics.jobs_by_site,
                'top_search_terms': metrics.top_search_terms,
                'alerts': [asdict(alert) for alert in alerts],
                'quota_usage': quota_result.data if quota_result.data else [],
                'recommendations': self._generate_recommendations(metrics, alerts)
            }
            
            # Store report
            report_data = {
                'date': datetime.now().date().isoformat(),
                'report_data': report,
                'created_at': datetime.now().isoformat()
            }
            
            self.supabase.table('daily_reports').upsert(report_data, on_conflict='date').execute()
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating daily report: {str(e)}")
            raise
    
    def _generate_recommendations(self, metrics: CollectionMetrics, alerts: List[Alert]) -> List[str]:
        """Generate actionable recommendations based on metrics and alerts"""
        recommendations = []
        
        if metrics.company_extraction_rate < 0.8:
            recommendations.append("Consider improving company name extraction algorithms or data sources")
        
        if metrics.duplicate_rate > 0.1:
            recommendations.append("Review deduplication logic and job_url_hash generation")
        
        if metrics.total_jobs < self.config.alert_thresholds['min_daily_jobs']:
            recommendations.append("Increase search frequency or expand search terms and locations")
        
        # Site-specific recommendations
        site_performance = {site: count for site, count in metrics.jobs_by_site.items()}
        if site_performance:
            best_performing_site = max(site_performance, key=site_performance.get)
            worst_performing_site = min(site_performance, key=site_performance.get)
            
            if site_performance[worst_performing_site] < site_performance[best_performing_site] * 0.3:
                recommendations.append(f"Investigate issues with {worst_performing_site} - significantly underperforming compared to {best_performing_site}")
        
        if any(alert.severity == 'critical' for alert in alerts):
            recommendations.append("Address critical alerts immediately - system may be failing")
        
        return recommendations

def run_health_check():
    """Run system health check and return results"""
    monitor = MonitoringSystem()
    
    try:
        metrics = monitor.collect_metrics(24)
        alerts = monitor.check_system_health()
        
        print(f"System Health Check - {datetime.now()}")
        print("="*50)
        print(f"Total jobs (24h): {metrics.total_jobs}")
        print(f"Company extraction rate: {metrics.company_extraction_rate:.1%}")
        print(f"Error rate: {metrics.error_rate:.1%}")
        print(f"Active alerts: {len(alerts)}")
        
        if alerts:
            print("\nActive Alerts:")
            for alert in alerts:
                print(f"  [{alert.severity.upper()}] {alert.message}")
        
        return {"metrics": metrics, "alerts": alerts}
        
    except Exception as e:
        print(f"Health check failed: {str(e)}")
        return None

if __name__ == "__main__":
    run_health_check()
