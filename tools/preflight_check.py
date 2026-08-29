# -*- coding: utf-8 -*-
"""
Static preflight checks for qimamhd_transportation_driver_delivery.

This does NOT replace installing/upgrading the module in an Odoo 13 test DB,
but it catches syntax/XML/reference mistakes before deployment.
"""

import ast
import csv
import py_compile
import sys
from collections import defaultdict
from pathlib import Path

from lxml import etree


MODULE = "qimamhd_transportation_driver_delivery"
ROOT = Path(__file__).resolve().parents[1]


def ok(label):
    print("[OK]   %s" % label)


def fail(label, detail):
    print("[FAIL] %s: %s" % (label, detail))
    return 1


def collect_python_models():
    fields_by_model = defaultdict(set)
    methods_by_model = defaultdict(set)

    for py in ROOT.rglob("*.py"):
        if py.name == "__manifest__.py":
            continue

        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))

        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue

            model_name = None
            inherit_name = None
            class_fields = set()
            class_methods = set()

            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    if (
                        len(stmt.targets) == 1
                        and isinstance(stmt.targets[0], ast.Name)
                        and stmt.targets[0].id in ("_name", "_inherit")
                    ):
                        try:
                            value = ast.literal_eval(stmt.value)
                        except Exception:
                            value = None

                        if stmt.targets[0].id == "_name" and isinstance(value, str):
                            model_name = value
                        elif stmt.targets[0].id == "_inherit" and isinstance(value, str):
                            inherit_name = value

                    if isinstance(stmt.value, ast.Call):
                        fn = stmt.value.func
                        if (
                            isinstance(fn, ast.Attribute)
                            and isinstance(fn.value, ast.Name)
                            and fn.value.id == "fields"
                        ):
                            for target in stmt.targets:
                                if isinstance(target, ast.Name):
                                    class_fields.add(target.id)

                elif isinstance(stmt, ast.FunctionDef):
                    class_methods.add(stmt.name)

            model = model_name or inherit_name
            if model:
                fields_by_model[model].update(class_fields)
                methods_by_model[model].update(class_methods)

    return fields_by_model, methods_by_model


def main():
    errors = 0

    # Python syntax/compile
    for py in sorted(ROOT.rglob("*.py")):
        try:
            py_compile.compile(str(py), doraise=True)
            ok("Python compile %s" % py.relative_to(ROOT))
        except Exception as exc:
            errors += fail("Python compile %s" % py.relative_to(ROOT), exc)

    fields_by_model, methods_by_model = collect_python_models()

    xml_ids = defaultdict(list)

    for xml in sorted(ROOT.rglob("*.xml")):
        rel = xml.relative_to(ROOT)

        try:
            doc = etree.parse(str(xml))
            ok("XML parse %s" % rel)
        except Exception as exc:
            errors += fail("XML parse %s" % rel, exc)
            continue

        for node in doc.xpath("//*[@id]"):
            if node.tag in ("record", "menuitem", "template"):
                xml_ids[node.get("id")].append(str(rel))

        # Exact Odoo 13 rule from odoo/tools/view_validation.py:
        # label nodes in form views require @for unless they contain an input.
        bad_labels = doc.xpath(
            "//field[@name='arch']//label[not(@for) and not(descendant::input)]"
        )
        if bad_labels:
            errors += fail(
                "Odoo13 label validation %s" % rel,
                "%s label(s) without @for" % len(bad_labels),
            )
        else:
            ok("Odoo13 label validation %s" % rel)

        # Validate XPath expression syntax.
        bad_xpath = []
        for node in doc.xpath("//field[@name='arch']//xpath[@expr]"):
            try:
                etree.XPath(node.get("expr"))
            except Exception as exc:
                bad_xpath.append("%s -> %s" % (node.get("expr"), exc))

        if bad_xpath:
            errors += fail("XPath syntax %s" % rel, "; ".join(bad_xpath))
        else:
            ok("XPath syntax %s" % rel)

        # Verify object buttons against methods declared by this module.
        for record in doc.xpath("//record[@model='ir.ui.view']"):
            model_node = record.xpath("./field[@name='model']")
            arch_node = record.xpath("./field[@name='arch']")
            if not model_node or not arch_node:
                continue

            model = (model_node[0].text or "").strip()
            if model not in methods_by_model:
                continue

            for button in arch_node[0].xpath(".//button[@type='object'][@name]"):
                name = button.get("name")
                if name not in methods_by_model[model]:
                    errors += fail(
                        "Object button method",
                        "%s.%s referenced in %s but not found"
                        % (model, name, rel),
                    )

    duplicates = {k: v for k, v in xml_ids.items() if len(v) > 1}
    if duplicates:
        errors += fail("Duplicate XML IDs", duplicates)
    else:
        ok("No duplicate XML IDs")

    # Manifest checks
    manifest_path = ROOT / "__manifest__.py"
    try:
        manifest = ast.literal_eval(manifest_path.read_text(encoding="utf-8"))
        ok("Manifest parse")
    except Exception as exc:
        errors += fail("Manifest parse", exc)
        manifest = {}

    if "qimamhd_transportation_v2_13" not in manifest.get("depends", []):
        errors += fail("Base dependency", "qimamhd_transportation_v2_13 missing")
    else:
        ok("Base dependency")

    for rel in manifest.get("data", []):
        if not (ROOT / rel).exists():
            errors += fail("Manifest data path", "%s does not exist" % rel)
        else:
            ok("Manifest data path %s" % rel)

    # Access CSV
    access_path = ROOT / "security" / "ir.model.access.csv"
    try:
        with access_path.open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        required = {
            "id",
            "name",
            "model_id:id",
            "group_id:id",
            "perm_read",
            "perm_write",
            "perm_create",
            "perm_unlink",
        }
        if not rows:
            errors += fail("Access CSV", "empty")
        elif set(rows[0]) != required:
            errors += fail("Access CSV", "invalid columns")
        else:
            ok("Access CSV")
    except Exception as exc:
        errors += fail("Access CSV", exc)

    # Old technical module name must not survive.
    old_name = "qimamhd_" + "driver_delivery_requests"
    leftovers = []
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix in (".py", ".xml", ".csv", ".md"):
            content = path.read_text(encoding="utf-8", errors="ignore")
            if old_name in content:
                leftovers.append(str(path.relative_to(ROOT)))

    if leftovers:
        errors += fail("Old module references", leftovers)
    else:
        ok("No old module references")

    print("")
    if errors:
        print("PREFLIGHT FAILED: %s error(s)" % errors)
        return 1

    print("PREFLIGHT PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
