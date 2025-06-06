"""
Course recommendation module for the SkillsTown CV Analyzer application.
"""

import json
import logging

logger = logging.getLogger(__name__)

class CourseRecommender:
    """
    A class to recommend courses based on extracted skills.
    """
    
    def __init__(self, catalog_path):
        """
        Initialize the course recommender.
        
        Args:
            catalog_path (str): Path to the JSON file containing the course catalog.
        """
        self.catalog_path = catalog_path
        self.catalog = self._load_catalog()
    
    def _load_catalog(self):
        """
        Load the course catalog from the JSON file.
        
        Returns:
            dict: The course catalog as a dictionary.
        """
        try:
            with open(self.catalog_path, 'r', encoding='utf-8') as f:
                catalog = json.load(f)
                logger.info(f"Loaded course catalog from {self.catalog_path}")
                
                # Log some statistics about the catalog
                categories = catalog.get('categories', [])
                total_courses = sum(len(category.get('courses', [])) for category in categories)
                logger.info(f"Catalog contains {len(categories)} categories and {total_courses} courses")
                
                return catalog
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading course catalog from {self.catalog_path}: {e}")
            return {"categories": []}
    
    def refresh_catalog(self):
        """
        Refresh the course catalog by reloading it from the file.
        """
        self.catalog = self._load_catalog()
    
    def recommend(self, skills, max_recommendations=10):
        """
        Recommend courses based on the given skills.
        
        Args:
            skills (list): List of skills to base recommendations on.
            max_recommendations (int): Maximum number of recommendations to return.
            
        Returns:
            list: A list of recommended courses, sorted by relevance.
        """
        if not skills:
            return []
        
        recommendations = []
        seen_courses = set()
        
        # Iterate through categories and courses
        for category in self.catalog.get('categories', []):
            for course in category.get('courses', []):
                # Create a unique key for each course to avoid duplicates
                course_key = f"{category['name']}:{course['name']}"
                
                if course_key in seen_courses:
                    continue
                
                # Find matching skills in course name and description
                course_name_lower = course['name'].lower()
                course_description_lower = course.get('description', '').lower()
                
                matching_skills = []
                for skill in skills:
                    if (skill in course_name_lower or 
                        skill in course_description_lower):
                        matching_skills.append(skill)
                
                # Add course to recommendations if it matches any skills
                if matching_skills:
                    recommendations.append({
                        'category': category['name'],
                        'course': course['name'],
                        'description': course.get('description', ''),
                        'matching_skills': list(dict.fromkeys(matching_skills)),
                        'match_score': len(matching_skills)
                    })
                    seen_courses.add(course_key)
        
        # Sort recommendations by match score (descending)
        sorted_recommendations = sorted(recommendations, key=lambda x: -x['match_score'])
        
        # Return the top recommendations
        return sorted_recommendations[:max_recommendations]