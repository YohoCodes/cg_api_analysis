

# Useful Search function
def Search(query, list_like, exact_match=False):
    results = []
    for item in list_like:
        if exact_match:
            if query.lower() == item.lower():
                results.append(item)
        else:
            if query.lower() in item.lower():
                results.append(item)
    return results