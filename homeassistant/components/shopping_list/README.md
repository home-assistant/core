# Shopping list integration

Home Assistant shopping List integration is built for users to create and manage shopping list from the Home Assistant UI. It supports adding ,completing and removing items to modify in the list.
The enhanced version adds support for predefined categories, user-created categories , adding items with quantity and units and also with other additional features.

# Existing features

- Add items to the shopping list
- Remove all the items from the list
- Mark items as complete or incomplete
- Mark the whole list of items as complete or incomplete
- Clear the list completely
- Sort the items in the list by name

# New features

- Add items to predefined categories
- Create new user-created categories
- Add quantity and unit to the categories
- Group items in the list by category
- Remove duplicate items in the category list
- Delete all items in the entire shopping list
- Remove predefined and user-created categories

# How the new features works

- Users can add item by viewing a list of predefined categories (eg., Fruit & Vegetables, Dairy, Bakery, etc.) when interacting with the shopping list.
- Users can create their own categories if none of the predefined ones fit their needs.
- Users can add the name of the item, category type, quantity and unit of the items.
- The items unit could be any of the specified units in the list. (eg.,pieces, grams, etc.)
- The items in the shopping list could be grouped by the category name.
- The list does not allow duplicate entries of the item.
- All items in the list could be deleted together.
- Users can remove both predefined and user-created categories in a list.

# File structure

- `__init__.py` - Purpose of the file is to set up the component setup, service registration and category initialization.
- `config_flow.py` - Implements the configuration flow enabling the UI based setup for the integration.
- `const.py` - Stores all the integration constants used throughout the shopping list integration.
-  `icons.json` - UI icons for category.
- `intent.py` — Supports voice and assist intents.
- `manifest.json` - Metadata describing the integration.
- `services.yaml` - Define the services available like (`add_item`, `remove_item`, `add_category`, etc.)
- `strings.json`  - UI strings for category labels.
- `todo.py` - Implements the backend logic for items, categories and storage.
- `.shopping_list.json` - Supports the storage of items and categories and gets automatically updated for the shopping list integration.
