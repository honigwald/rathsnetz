from datetime import datetime, timedelta
import logging
import json

from django.db import models
from django.utils import timezone
from django.conf import settings

from brewery.models import Preparation
from brewery.models import RecipeBrewStep

from brewery.utils import load_dynamic_bg_image

# Get logger for this module
logger = logging.getLogger(__name__)


class Recipe(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=25)
    creation = models.DateTimeField(default=timezone.now)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, blank=True, null=True
    )
    hg = models.FloatField()
    ng = models.FloatField()
    head = models.ForeignKey(
        RecipeBrewStep, related_name="recipe_head", on_delete=models.SET_NULL, null=True
    )
    tail = models.ForeignKey(
        RecipeBrewStep, related_name="recipe_tail", on_delete=models.SET_NULL, null=True
    )
    wort = models.FloatField()
    ibu = models.FloatField()
    boiltime = models.DurationField()
    preps = models.ManyToManyField(Preparation, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-creation']
        verbose_name = "Recipe"
        verbose_name_plural = "Recipes"

    def clean(self):
        """Validate model data"""
        from django.core.exceptions import ValidationError

        if self.hg and self.hg <= 0:
            raise ValidationError({'hg': 'Hauptguss must be positive'})
        if self.ng and self.ng <= 0:
            raise ValidationError({'ng': 'Nachguss must be positive'})
        if self.wort and self.wort <= 0:
            raise ValidationError({'wort': 'Wort gravity must be positive'})
        if self.ibu and self.ibu < 0:
            raise ValidationError({'ibu': 'IBU cannot be negative'})

    @property
    def total_water(self):
        """Calculate total water needed"""
        return (self.hg or 0) + (self.ng or 0)

    @property
    def step_count(self):
        """Get number of steps in recipe"""
        steps = self.steps()
        return len(list(steps)) if steps else 0

    def preparations(self):
        return self.preps.values()
        # return Preparation.objects.filter(recipe=self)

    def add_preparation(self, prep: Preparation):
        self.preps.add(prep)

    def steps(self):
        if self.head is not None:
            return self.head.dict().values()
        else:
            return None

    def steps_with_hops(self):
        hopsteps = []
        if self.steps():
            for step in self.steps():
                if step.ingredient and step.ingredient.type.name == "Hopfen":
                    hopsteps.append(step)
        logger.debug("Found hop steps: %s", hopsteps)
        return hopsteps

    def est_during_boiltime(self, curr_step):
        """Calculate estimated time during boil for a specific step"""
        est = 0
        if not self.steps():
            return est

        for step in self.steps():
            if step.duration and hasattr(step, 'category') and step.category and step.category.name == "Würzekochung":
                est += step.duration.total_seconds()
            if step == curr_step:
                return est
        return est

    def step_by_id(self, sid: int):
        return self.head.dict().get(sid)

    def update_step_number(self):
        self.refresh_from_db()
        i = 1
        if self.steps():
            for s in self.steps():
                logger.debug("update_step_number(): [%s] %s -> %s", s, s.pos, i)
                s.pos = i
                s.rname = self.name  # ensure recipe name is set
                s.save()
                i += 1

    def query(self):
        return RecipeBrewStep.objects.filter(rname=self.name)

    def add_to_front(self, step: RecipeBrewStep):
        if step == self.head:
            return

        if step == self.tail:
            self.tail = step.previous
            self.save()

        step.unlink_from_list()

        if self.head is None:
            self.head = step
            self.tail = step
        else:
            self.refresh_from_db()
            step.link_between(None, self.head)
            self.head = step

        step.recipe_name(self.name)
        step.save()
        self.save()

    def add_to_end(self, step: RecipeBrewStep):
        if step == self.tail:
            return

        if step == self.head:
            self.head = step.next
            self.save()

        step.unlink_from_list()

        if self.tail is None:
            self.head = step
            self.tail = step
        else:
            self.refresh_from_db()
            step.link_between(self.tail, None)
            self.tail = step

        step.recipe_name(self.name)
        step.save()
        self.save()

    def add_in_between(self, predecessor: RecipeBrewStep, step: RecipeBrewStep):
        if predecessor is None:
            return

        if step == predecessor.next:
            return

        if step == self.head:
            self.head = step.next
            self.head.previous = None
            self.save()
        if step == self.tail:
            self.tail = step.previous
            self.save()
            self.refresh_from_db()
            self.tail.next = None
            self.save()

        step.unlink_from_list()
        predecessor.refresh_from_db()
        step.link_between(predecessor, predecessor.next)
        step.recipe_name(self.name)
        step.save()

    def context(self):
        context = {}
        context["recipe"] = self
        context["steps"] = self.steps()
        context["preparation"] = self.preparations()
        context["navi"] = "recipe"
        context["image_url"] = load_dynamic_bg_image()

        return context

    def export_json(self):
        """Export recipe data as JSON format with error handling"""
        try:
            recipe_data = {
                "recipe": {
                    "name": self.name,
                    "author": str(self.author) if self.author else None,
                    "creation": self.creation.isoformat() if self.creation else None,
                    "export_date": datetime.now().isoformat(),
                    "hg": float(self.hg) if self.hg else 0.0,
                    "ng": float(self.ng) if self.ng else 0.0,
                    "wort": float(self.wort) if self.wort else 0.0,
                    "ibu": float(self.ibu) if self.ibu else 0.0,
                    "boiltime_seconds": self.boiltime.total_seconds() if self.boiltime else None,
                    "total_water": self.total_water,
                    "step_count": self.step_count,
                    "preparations": [],
                    "steps": []
                }
            }

            # Add preparations with error handling
            try:
                for prep in self.preparations():
                    recipe_data["recipe"]["preparations"].append({
                        "id": prep.get("id"),
                        "short": prep.get("short", ""),
                        "detail": prep.get("detail", "")
                    })
            except Exception as e:
                logger.warning("Error processing preparations: %s", e)

            # Add steps with comprehensive error handling
            if self.steps():
                try:
                    for i, step in enumerate(self.steps(), 1):
                        step_data = {
                            "position": i,
                            "title": getattr(step, 'title', ''),
                            "description": getattr(step, 'description', ''),
                            "amount": float(step.amount) if step.amount else None,
                            "unit": str(step.unit) if step.unit else None,
                            "duration_seconds": step.duration.total_seconds() if step.duration else None,
                            "category": step.category.name if hasattr(step, 'category') and step.category else None
                        }

                        # Handle ingredient data safely
                        if hasattr(step, 'ingredient') and step.ingredient:
                            ingredient_data = {
                                "name": step.ingredient.name,
                                "type": step.ingredient.type.name if hasattr(step.ingredient, 'type') and step.ingredient.type else None
                            }
                            # Add alpha value if it exists (for hops)
                            if hasattr(step.ingredient, 'alpha') and step.ingredient.alpha:
                                ingredient_data["alpha"] = float(step.ingredient.alpha)
                            step_data["ingredient"] = ingredient_data
                        else:
                            step_data["ingredient"] = None

                        recipe_data["recipe"]["steps"].append(step_data)
                except Exception as e:
                    logger.error("Error processing steps: %s", e)

            return json.dumps(recipe_data, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error("Error in export_json: %s", e)
            # Return minimal valid JSON on error
            return json.dumps({
                "recipe": {
                    "name": self.name,
                    "error": f"Export failed: {str(e)}"
                }
            }, indent=2)

    @classmethod
    def import_json(cls, json_data, user=None, update_existing=False):
        """Import recipe data from JSON format"""
        from django.db import transaction

        try:
            # Parse JSON if it's a string
            if isinstance(json_data, str):
                data = json.loads(json_data)
            else:
                data = json_data

            if 'recipe' not in data:
                raise ValueError("Invalid JSON format: missing 'recipe' key")

            recipe_data = data['recipe']

            # Check for required fields
            if 'name' not in recipe_data:
                raise ValueError("Recipe name is required")

            # Use transaction to ensure atomicity
            with transaction.atomic():
                # Check if recipe already exists
                recipe_name = recipe_data['name']
                if update_existing:
                    try:
                        recipe = cls.objects.get(name=recipe_name)
                        logger.info("Updating existing recipe: %s", recipe_name)
                    except cls.DoesNotExist:
                        recipe = cls()
                        logger.info("Creating new recipe: %s", recipe_name)
                else:
                    # Check if recipe already exists
                    if cls.objects.filter(name=recipe_name).exists():
                        raise ValueError(f"Recipe '{recipe_name}' already exists. Use update_existing=True to update.")
                    recipe = cls()
                    logger.info("Creating new recipe: %s", recipe_name)

                # Set basic recipe fields
                recipe.name = recipe_name
                recipe.author = user
                recipe.hg = float(recipe_data.get('hg', 0))
                recipe.ng = float(recipe_data.get('ng', 0))
                recipe.wort = float(recipe_data.get('wort', 0))
                recipe.ibu = float(recipe_data.get('ibu', 0))

                # Handle boiltime - provide default if not specified
                boiltime_seconds = recipe_data.get('boiltime_seconds')
                if boiltime_seconds:
                    from datetime import timedelta
                    recipe.boiltime = timedelta(seconds=float(boiltime_seconds))
                else:
                    # Default to 60 minutes if not specified
                    from datetime import timedelta
                    recipe.boiltime = timedelta(minutes=60)
                    logger.info("No boiltime specified, using default of 60 minutes")

                # Validate and save recipe
                recipe.clean()
                recipe.save()

                # Import preparations
                preparations_data = recipe_data.get('preparations', [])
                if preparations_data:
                    recipe._import_preparations(preparations_data)

                # Import steps
                steps_data = recipe_data.get('steps', [])
                if steps_data:
                    recipe._import_steps(steps_data)

                logger.info("Successfully imported recipe: %s", recipe.name)
                return recipe

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON format: %s", e)
            raise ValueError(f"Invalid JSON format: {str(e)}")
        except Exception as e:
            logger.error("Error importing recipe: %s", e)
            raise ValueError(f"Import failed: {str(e)}")

    def _import_preparations(self, preparations_data):
        """Import preparations for this recipe"""
        from brewery.models import Preparation
        from django.db import transaction

        logger.info("Importing %d preparations for recipe %s", len(preparations_data), self.name)

        # Use transaction to ensure atomicity
        with transaction.atomic():
            # Clear existing preparations if updating
            self.preps.clear()

            for prep_data in preparations_data:
                try:
                    # Try to find existing preparation by short name
                    short = prep_data.get('short', '')
                    detail = prep_data.get('detail', '')

                    logger.debug("Processing preparation: short='%s', detail='%s'", short, detail)

                    if short:
                        prep, created = Preparation.objects.get_or_create(
                            short=short,
                            defaults={'detail': detail}
                        )
                        self.add_preparation(prep)
                        if created:
                            logger.info("Created new preparation: %s", short)
                        else:
                            logger.info("Using existing preparation: %s", short)
                    else:
                        logger.warning("Skipping preparation with empty short name: %s", prep_data)

                except Exception as e:
                    logger.error("Error importing preparation %s: %s", prep_data, e)

            # Save the recipe to persist the many-to-many relationships
            self.save()

        logger.info("Successfully imported preparations for recipe %s. Total preparations: %d",
                   self.name, self.preps.count())

    def _import_steps(self, steps_data):
        """Import steps for this recipe"""
        from brewery.models import RecipeBrewStep, Category, Storage, Unit

        # Clear existing steps if updating
        if self.head:
            # Remove all existing steps
            current = self.head
            while current:
                next_step = current.next
                current.delete()
                current = next_step
            self.head = None
            self.tail = None
            self.save()

        # Sort steps by position
        steps_data.sort(key=lambda x: x.get('position', 0))

        for step_data in steps_data:
            try:
                # Create new step
                step = RecipeBrewStep()
                step.pos = step_data.get('position', 1)
                step.title = step_data.get('title', '')
                step.description = step_data.get('description', '')
                step.rname = self.name

                # Handle amount
                amount = step_data.get('amount')
                if amount is not None:
                    step.amount = float(amount)

                # Handle duration
                duration_seconds = step_data.get('duration_seconds')
                if duration_seconds:
                    from datetime import timedelta
                    step.duration = timedelta(seconds=float(duration_seconds))

                # Handle category
                category_name = step_data.get('category')
                if category_name:
                    try:
                        category = Category.objects.get(name=category_name)
                        step.category = category
                    except Category.DoesNotExist:
                        logger.warning("Category '%s' not found, creating new one", category_name)
                        category = Category.objects.create(name=category_name)
                        step.category = category

                # Handle unit
                unit_name = step_data.get('unit')
                if unit_name:
                    try:
                        unit = Unit.objects.get(name=unit_name)
                        step.unit = unit
                    except Unit.DoesNotExist:
                        logger.warning("Unit '%s' not found, creating new one", unit_name)
                        unit = Unit.objects.create(name=unit_name)
                        step.unit = unit

                # Handle ingredient
                ingredient_data = step_data.get('ingredient')
                if ingredient_data and ingredient_data.get('name'):
                    try:
                        ingredient = Storage.objects.get(name=ingredient_data['name'])
                        step.ingredient = ingredient
                    except Storage.DoesNotExist:
                        logger.warning("Ingredient '%s' not found in storage, creating new one", ingredient_data['name'])
                        # Create new ingredient
                        from brewery.models import Type

                        # Get or create ingredient type
                        ingredient_type_name = ingredient_data.get('type', 'Unknown')
                        ingredient_type, type_created = Type.objects.get_or_create(
                            name=ingredient_type_name
                        )
                        if type_created:
                            logger.debug("Created new ingredient type: %s", ingredient_type_name)

                        # Get default unit (use step unit if available, otherwise create 'g')
                        default_unit = step.unit
                        if not default_unit:
                            default_unit, unit_created = Unit.objects.get_or_create(name='g')
                            if unit_created:
                                logger.debug("Created default unit: g")

                        # Create the ingredient in storage
                        ingredient = Storage.objects.create(
                            name=ingredient_data['name'],
                            type=ingredient_type,
                            amount=0,  # Start with 0 amount
                            unit=default_unit,
                            alpha=float(ingredient_data.get('alpha', 0)) if ingredient_data.get('alpha') else None
                        )
                        step.ingredient = ingredient
                        logger.info("Created new ingredient: %s (type: %s)", ingredient.name, ingredient_type.name)

                # Save step and add to recipe
                step.save()
                self.add_to_end(step)
                logger.debug("Imported step: %s", step.title or step.description)

            except Exception as e:
                logger.error("Error importing step %s: %s", step_data, e)