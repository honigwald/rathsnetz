import logging
import json
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from datetime import timedelta

from brewery.models import Recipe, RecipeBrewStep, Category, Preparation, Unit, Storage
from brewery.models.type import Type


class RecipeTest(TestCase):
    def setUp(self):
        logging.disable(logging.DEBUG)
        # Set up any necessary data before each test
        duration = timedelta(days=2, hours=5, minutes=30)

        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Create test recipe
        self.recipe = Recipe.objects.create(
            name="Helles",
            creation=timezone.now(),
            author=self.user,
            hg=10,
            ng=20,
            wort=22,
            ibu=15,
            boiltime=duration,
        )

        # Create test categories
        self.category = Category.objects.create(name="test_cat")
        self.hop_category = Category.objects.create(name="Würzekochung")

        # Create test types
        self.hop_type = Type.objects.create(name="Hopfen")
        self.malt_type = Type.objects.create(name="Malz")

        # Create test units
        self.gram_unit = Unit.objects.create(name="g")
        self.kg_unit = Unit.objects.create(name="kg")

        # Create test preparations
        self.prep1 = Preparation.objects.create(
            short="Prep 1",
            detail="Test preparation 1"
        )
        self.prep2 = Preparation.objects.create(
            short="Prep 2",
            detail="Test preparation 2"
        )

        # Create test storage items
        self.hop_storage = Storage.objects.create(
            name="Test Hop",
            amount=500,
            unit=self.gram_unit,
            type=self.hop_type,
            alpha=5.2
        )

    def test_recipe_data(self):
        recipe = Recipe.objects.get(name="Helles")
        self.assertEqual(recipe.ng, 20)
        self.assertEqual(recipe.ibu, 15)
        self.assertEqual(recipe.head, None)
        self.assertEqual(recipe.tail, None)
        self.assertEqual(recipe.author, self.user)

    def test_add_step_to_front(self):
        recipe = Recipe.objects.get(name="Helles")
        cat = Category.objects.get(name="test_cat")
        s1 = RecipeBrewStep.objects.create(pos=1, category=cat)
        s2 = RecipeBrewStep.objects.create(pos=2, category=cat)
        recipe.add_to_front(s1)

        self.assertEqual(recipe.head, s1)
        self.assertEqual(recipe.tail, s1)

        recipe.add_to_front(s2)
        self.assertEqual(recipe.head, s2)
        self.assertEqual(recipe.tail, s1)
        self.assertEqual(recipe.head.next, s1)
        self.assertEqual(recipe.tail.previous, s2)

    def test_add_step_as_tail(self):
        recipe = Recipe.objects.get(name="Helles")
        cat = Category.objects.get(name="test_cat")
        head = RecipeBrewStep.objects.create(pos=1, category=cat)
        tail = RecipeBrewStep.objects.create(pos=2, category=cat)

        recipe.add_to_front(head)
        recipe.add_to_end(tail)
        self.assertEqual(recipe.head, head)
        self.assertEqual(recipe.tail, tail)
        self.assertEqual(recipe.head.next, tail)
        self.assertEqual(recipe.tail.previous, head)

        self.assertEqual(len(recipe.steps()), 2)

    def test_insert_three_in_a_row(self):
        recipe = Recipe.objects.get(name="Helles")
        cat = Category.objects.get(name="test_cat")
        head = RecipeBrewStep.objects.create(pos=1, category=cat)
        middle = RecipeBrewStep.objects.create(pos=2, category=cat)
        tail = RecipeBrewStep.objects.create(pos=3, category=cat)

        recipe.add_to_front(head)
        recipe.add_to_end(middle)
        recipe.add_to_end(tail)
        head.refresh_from_db()
        middle.refresh_from_db()
        tail.refresh_from_db()
        self.assertEqual(recipe.head, head)
        self.assertEqual(recipe.tail, tail)
        self.assertEqual(len(recipe.steps()), 3)

        self.assertEqual(head.next, middle)
        self.assertEqual(middle.next, tail)
        self.assertEqual(tail.next, None)

        self.assertEqual(head.previous, None)
        self.assertEqual(middle.previous, head)
        self.assertEqual(tail.previous, middle)

    def test_insert_step_in_between(self):
        # prime recipe with three steps
        recipe = Recipe.objects.get(name="Helles")
        cat = Category.objects.get(name="test_cat")
        head = RecipeBrewStep.objects.create(pos=1, category=cat)
        middle = RecipeBrewStep.objects.create(pos=2, category=cat)
        tail = RecipeBrewStep.objects.create(pos=3, category=cat)

        recipe.add_to_front(head)
        recipe.add_to_end(middle)
        recipe.add_to_end(tail)
        head.refresh_from_db()
        middle.refresh_from_db()
        tail.refresh_from_db()

        self.assertEqual(recipe.head, head)
        self.assertEqual(recipe.tail, tail)
        self.assertEqual(len(recipe.steps()), 3)

        in_between = RecipeBrewStep.objects.create(pos=23, category=cat)
        recipe.add_in_between(predecessor=middle, step=in_between)

        recipe.refresh_from_db()
        self.assertEqual(len(recipe.steps()), 4)
        test_pos_data = [1, 2, 23, 3]
        i = 0
        for s in recipe.steps():
            self.assertEqual(s.pos, test_pos_data[i])
            i = i + 1

    def prime_recipe_with_steps(self, r: Recipe, steps: int):
        cat = Category.objects.get(name="test_cat")
        for i in range(steps):
            new_step = RecipeBrewStep(category=cat)
            r.add_to_end(new_step)
        r.update_step_number()
        self.assertEqual(len(r.steps()), steps)

    def test_move_step_from_in_between_to_head(self):
        # prime recipe with 4 steps
        r = Recipe.objects.get(name="Helles")
        self.prime_recipe_with_steps(r, 4)

        head = r.head
        s3 = RecipeBrewStep.objects.get(pos=3)
        r.add_to_front(s3)
        self.assertEqual(r.head, s3)
        self.assertEqual(r.head.next, head)

    def test_move_step_from_in_between_to_tail(self):
        # prime recipe with 4 steps
        r = Recipe.objects.get(name="Helles")
        self.prime_recipe_with_steps(r, 4)

        r.update_step_number()
        tail = r.tail
        s3 = RecipeBrewStep.objects.get(pos=3)
        r.add_to_end(s3)
        self.assertEqual(r.tail, s3)
        self.assertEqual(r.tail.previous, tail)

    def test_move_step_from_head_to_tail(self):
        # prime recipe with 4 steps
        r = Recipe.objects.get(name="Helles")
        self.prime_recipe_with_steps(r, 4)

        head = r.head
        new_head = head.next
        tail = r.tail

        r.add_to_end(head)
        tail.refresh_from_db()
        self.assertEqual(r.head, new_head)
        self.assertEqual(r.tail, head)
        self.assertEqual(tail.next, head)
        self.assertEqual(head.previous, tail)
        self.assertEqual(head.next, None)
        self.assertEqual(r.head.pos, 2)
        self.assertEqual(r.tail.pos, 1)

    def test_move_step_from_tail_to_head(self):
        # prime recipe with 4 steps
        r = Recipe.objects.get(name="Helles")
        self.prime_recipe_with_steps(r, 4)
        r.refresh_from_db()

        tail = r.tail
        new_tail = tail.previous
        head = r.head

        r.add_to_front(tail)
        head.refresh_from_db()
        self.assertEqual(r.tail, new_tail)
        self.assertEqual(new_tail.next, None)
        self.assertEqual(r.head, tail)
        self.assertEqual(r.head.next, head)
        self.assertEqual(head.previous, tail)

    def test_move_head_to_in_between(self):
        # prime recipe with 4 steps
        r = Recipe.objects.get(name="Helles")
        self.prime_recipe_with_steps(r, 4)
        r.refresh_from_db()

        head = r.head
        new_head = head.next
        s3 = RecipeBrewStep.objects.get(pos=3)
        r.add_in_between(predecessor=s3, step=head)
        r.refresh_from_db()
        self.assertEqual(r.head, new_head)
        self.assertEqual(head.previous, s3)
        self.assertEqual(s3.next, head)

    def test_move_tail_to_in_between(self):
        # prime recipe with 4 steps
        r = Recipe.objects.get(name="Helles")
        self.prime_recipe_with_steps(r, 4)
        r.refresh_from_db()

        tail = r.tail
        s2 = RecipeBrewStep.objects.get(pos=1)
        r.add_in_between(predecessor=s2, step=tail)
        r.refresh_from_db()
        tail.refresh_from_db()

    def test_recipe_str_method(self):
        """Test the __str__ method returns recipe name"""
        recipe = Recipe.objects.get(name="Helles")
        self.assertEqual(str(recipe), "Helles")

    def test_recipe_properties(self):
        """Test recipe properties"""
        recipe = Recipe.objects.get(name="Helles")
        self.assertEqual(recipe.total_water, 30)  # hg + ng = 10 + 20
        self.assertEqual(recipe.step_count, 0)  # No steps added yet

        # Add a step and test step_count
        step = RecipeBrewStep.objects.create(pos=1, category=self.category)
        recipe.add_to_front(step)
        self.assertEqual(recipe.step_count, 1)

    def test_recipe_validation(self):
        """Test recipe validation rules"""
        recipe = Recipe.objects.get(name="Helles")

        # Test negative values
        recipe.hg = -5
        with self.assertRaises(ValidationError):
            recipe.clean()

        recipe.hg = 10  # Reset
        recipe.ng = -10
        with self.assertRaises(ValidationError):
            recipe.clean()

        recipe.ng = 20  # Reset
        recipe.ibu = -5
        with self.assertRaises(ValidationError):
            recipe.clean()

    def test_preparations_functionality(self):
        """Test recipe preparations management"""
        recipe = Recipe.objects.get(name="Helles")

        # Add preparations
        recipe.add_preparation(self.prep1)
        recipe.add_preparation(self.prep2)

        # Test preparations method
        preps = list(recipe.preparations())
        self.assertEqual(len(preps), 2)

        # Check if preparation shorts are in the results
        prep_shorts = [prep['short'] for prep in preps]
        self.assertIn("Prep 1", prep_shorts)
        self.assertIn("Prep 2", prep_shorts)

    def test_steps_with_hops(self):
        """Test filtering steps that contain hops"""
        recipe = Recipe.objects.get(name="Helles")

        # Create hop step
        hop_step = RecipeBrewStep.objects.create(
            pos=1,
            category=self.hop_category,
            ingredient=self.hop_storage,
            amount=30,
            unit=self.gram_unit
        )

        # Create non-hop step
        regular_step = RecipeBrewStep.objects.create(
            pos=2,
            category=self.category
        )

        recipe.add_to_front(hop_step)
        recipe.add_to_end(regular_step)

        hop_steps = recipe.steps_with_hops()
        self.assertEqual(len(hop_steps), 1)
        self.assertEqual(hop_steps[0], hop_step)

    def test_est_during_boiltime(self):
        """Test estimated time calculation during boil"""
        recipe = Recipe.objects.get(name="Helles")

        # Create steps with durations
        step1 = RecipeBrewStep.objects.create(
            pos=1,
            category=self.hop_category,  # Würzekochung category
            duration=timedelta(minutes=60)
        )
        step2 = RecipeBrewStep.objects.create(
            pos=2,
            category=self.hop_category,  # Würzekochung category
            duration=timedelta(minutes=30)
        )
        step3 = RecipeBrewStep.objects.create(
            pos=3,
            category=self.category,  # Non-boil category
            duration=timedelta(minutes=15)
        )

        recipe.add_to_front(step1)
        recipe.add_to_end(step2)
        recipe.add_to_end(step3)

        # Test EST calculation - the method accumulates time INCLUDING the current step
        # when it has the "Würzekochung" category
        est_step1 = recipe.est_during_boiltime(step1)
        self.assertEqual(est_step1, 3600)  # step1's own 60 minutes

        est_step2 = recipe.est_during_boiltime(step2)
        self.assertEqual(est_step2, 5400)  # 60 + 30 minutes in seconds

        est_step3 = recipe.est_during_boiltime(step3)
        self.assertEqual(est_step3, 5400)  # Still 60 + 30 minutes (step3 is not "Würzekochung")

    def test_export_json_basic(self):
        """Test basic JSON export functionality"""
        recipe = Recipe.objects.get(name="Helles")
        json_str = recipe.export_json()

        # Parse JSON to verify it's valid
        data = json.loads(json_str)

        # Check basic structure
        self.assertIn('recipe', data)
        recipe_data = data['recipe']

        # Check required fields
        self.assertEqual(recipe_data['name'], 'Helles')
        self.assertEqual(recipe_data['hg'], 10.0)
        self.assertEqual(recipe_data['ng'], 20.0)
        self.assertEqual(recipe_data['total_water'], 30.0)
        self.assertEqual(recipe_data['step_count'], 0)

        # Check if export_date is present
        self.assertIn('export_date', recipe_data)

    def test_export_json_with_steps_and_preparations(self):
        """Test JSON export with steps and preparations"""
        recipe = Recipe.objects.get(name="Helles")

        # Add preparations
        recipe.add_preparation(self.prep1)

        # Add a step with ingredient
        step = RecipeBrewStep.objects.create(
            pos=1,
            category=self.hop_category,
            ingredient=self.hop_storage,
            amount=30,
            unit=self.gram_unit,
            duration=timedelta(minutes=15),
            title="Add Hops",
            description="Add bittering hops"
        )
        recipe.add_to_front(step)

        json_str = recipe.export_json()
        data = json.loads(json_str)
        recipe_data = data['recipe']

        # Check preparations
        self.assertEqual(len(recipe_data['preparations']), 1)
        self.assertEqual(recipe_data['preparations'][0]['short'], 'Prep 1')

        # Check steps
        self.assertEqual(len(recipe_data['steps']), 1)
        step_data = recipe_data['steps'][0]
        self.assertEqual(step_data['position'], 1)
        self.assertEqual(step_data['title'], 'Add Hops')
        self.assertEqual(step_data['amount'], 30.0)
        self.assertEqual(step_data['duration_seconds'], 900)  # 15 minutes

        # Check ingredient data
        self.assertIsNotNone(step_data['ingredient'])
        self.assertEqual(step_data['ingredient']['name'], 'Test Hop')
        self.assertEqual(step_data['ingredient']['type'], 'Hopfen')
        self.assertEqual(step_data['ingredient']['alpha'], 5.2)

    def test_export_json_error_handling(self):
        """Test JSON export error handling"""
        recipe = Recipe.objects.get(name="Helles")

        # Test with None values
        recipe.hg = None
        recipe.ng = None
        json_str = recipe.export_json()
        data = json.loads(json_str)

        # Should handle None values gracefully
        self.assertEqual(data['recipe']['hg'], 0.0)
        self.assertEqual(data['recipe']['ng'], 0.0)

    def test_step_by_id(self):
        """Test finding step by ID"""
        recipe = Recipe.objects.get(name="Helles")
        step = RecipeBrewStep.objects.create(pos=1, category=self.category)
        recipe.add_to_front(step)

        found_step = recipe.step_by_id(step.id)
        self.assertEqual(found_step, step)

    def test_context_method(self):
        """Test context method for template rendering"""
        recipe = Recipe.objects.get(name="Helles")
        context = recipe.context()

        self.assertIn('recipe', context)
        self.assertIn('steps', context)
        self.assertIn('preparation', context)
        self.assertIn('navi', context)
        self.assertIn('image_url', context)

        self.assertEqual(context['recipe'], recipe)
        self.assertEqual(context['navi'], 'recipe')

    def test_update_step_number_with_steps(self):
        """Test step number updating functionality"""
        recipe = Recipe.objects.get(name="Helles")

        # Create steps with random positions
        step1 = RecipeBrewStep.objects.create(pos=99, category=self.category)
        step2 = RecipeBrewStep.objects.create(pos=55, category=self.category)
        step3 = RecipeBrewStep.objects.create(pos=11, category=self.category)

        recipe.add_to_front(step1)
        recipe.add_to_end(step2)
        recipe.add_to_end(step3)

        # Update step numbers
        recipe.update_step_number()

        # Refresh from DB and check positions
        step1.refresh_from_db()
        step2.refresh_from_db()
        step3.refresh_from_db()

        self.assertEqual(step1.pos, 1)
        self.assertEqual(step2.pos, 2)
        self.assertEqual(step3.pos, 3)

        # Check recipe names are set
        self.assertEqual(step1.rname, recipe.name)
        self.assertEqual(step2.rname, recipe.name)
        self.assertEqual(step3.rname, recipe.name)

    def test_empty_recipe_methods(self):
        """Test methods on empty recipe (no steps)"""
        recipe = Recipe.objects.get(name="Helles")

        # Test methods with no steps
        self.assertIsNone(recipe.steps())
        self.assertEqual(len(recipe.steps_with_hops()), 0)
        self.assertEqual(recipe.step_count, 0)
        self.assertEqual(recipe.est_during_boiltime(None), 0)

    def test_query_method(self):
        """Test query method returns correct QuerySet"""
        recipe = Recipe.objects.get(name="Helles")
        step = RecipeBrewStep.objects.create(pos=1, category=self.category, rname=recipe.name)

        queryset = recipe.query()
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first(), step)

    def test_recipe_meta_options(self):
        """Test model Meta options"""
        # Test ordering
        recipe1 = Recipe.objects.create(
            name="Recipe1",
            hg=10, ng=10, wort=12, ibu=20,
            boiltime=timedelta(hours=1),
            creation=timezone.now() - timedelta(days=1)
        )
        recipe2 = Recipe.objects.create(
            name="Recipe2",
            hg=15, ng=15, wort=14, ibu=25,
            boiltime=timedelta(hours=1),
            creation=timezone.now()
        )

        # Should be ordered by creation date descending
        recipes = list(Recipe.objects.all())
        self.assertEqual(recipes[0], recipe2)  # Most recent first

    def test_edge_cases_linked_list_operations(self):
        """Test edge cases in linked list operations"""
        recipe = Recipe.objects.get(name="Helles")
        step = RecipeBrewStep.objects.create(pos=1, category=self.category)

        # Test adding same step multiple times
        recipe.add_to_front(step)
        original_head = recipe.head
        recipe.add_to_front(step)  # Should not change anything
        self.assertEqual(recipe.head, original_head)

        # Test adding None predecessor
        new_step = RecipeBrewStep.objects.create(pos=2, category=self.category)
        recipe.add_in_between(None, new_step)  # Should return early
        self.assertEqual(recipe.step_count, 1)  # No change
