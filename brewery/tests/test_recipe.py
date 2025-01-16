import logging
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from brewery.models import Recipe, RecipeBrewStep, Category


class RecipeTest(TestCase):
    def setUp(self):
        logging.disable(logging.DEBUG)
        # Set up any necessary data before each test
        duration = timedelta(days=2, hours=5, minutes=30)
        Recipe.objects.create(
            name="Helles",
            creation=timezone.now(),
            hg=10,
            ng=20,
            wort=22,
            ibu=15,
            boiltime=duration,
        )
        Category.objects.create(name="test_cat")

    def test_recipe_data(self):
        recipe = Recipe.objects.get(name="Helles")
        self.assertEqual(recipe.ng, 20)
        self.assertEqual(recipe.ibu, 15)
        self.assertEqual(recipe.head, None)
        self.assertEqual(recipe.tail, None)

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

        print(r.steps())
        head = r.head
        new_head = head.next
        s3 = RecipeBrewStep.objects.get(pos=3)
        r.add_in_between(predecessor=s3, step=head)
        r.refresh_from_db()
        self.assertEqual(r.head, new_head)
        self.assertEqual(head.previous, s3)
        self.assertEqual(s3.next, head)
        print(r.steps())

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
