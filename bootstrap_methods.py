import io
import logging
import functools
from dataclasses import dataclass
from typing import BinaryIO, List, Tuple
from struct import unpack

# --- Lawu imports ---
# We need to import the real function so we can wrap it
from lawu.cf import ClassFile as Class
from lawu.constants import Constant
from lawu._instruction import Instruction
import lawu.attribute as attribute

logger = logging.getLogger(__name__)

# --- STEP 1: Define our custom parser class in the way lawu expects ---


@dataclass
class BootstrapMethod:
    """A dataclass to cleanly store the contents of a single bootstrap method entry."""
    method_ref: Constant
    arguments: List[Constant]


class BootstrapMethodsAttribute(attribute.Attribute):
    """
    Parses the `BootstrapMethods` attribute from a class file, following the
    design patterns of the `lawu` library.
    """
    # The official name of the attribute in the class file spec
    ATTRIBUTE_NAME = "BootstrapMethods"

    # Metadata required by the `lawu` framework
    ADDED_IN = '1.7'
    MINIMUM_CLASS_VERSION: Tuple[int, int] = (51, 0)

    def __init__(self, bootstrap_methods: List[BootstrapMethod]):
        """
        A simple data-holding constructor. The parsing is done in `from_binary`.
        """
        self.bootstrap_methods = bootstrap_methods

    def __repr__(self):
        return f"<BootstrapMethodsAttribute(methods={len(self.bootstrap_methods)})>"

    @classmethod
    def from_binary(cls, pool: List[Constant], source: BinaryIO) -> 'BootstrapMethodsAttribute':
        """
        The main parser, called by `lawu`'s attribute reading logic.
        It reads the binary payload and constructs an instance of this class.
        """
        # Read the number of bootstrap methods (u2 = unsigned short)
        num_methods, = unpack('>H', source.read(2))

        parsed_methods = []
        for _ in range(num_methods):
            # Read the bootstrap_method_ref (u2 index into the constant pool)
            method_ref_index, = unpack('>H', source.read(2))
            method_ref = pool[method_ref_index]

            # Read the number of arguments for this bootstrap method (u2)
            num_args, = unpack('>H', source.read(2))
            
            args = []
            for _ in range(num_args):
                # Read each argument (u2 index into the constant pool)
                arg_index, = unpack('>H', source.read(2))
                args.append(pool[arg_index])
            
            parsed_methods.append(BootstrapMethod(method_ref=method_ref, arguments=args))
        
        # Return an instance of this class, populated with the parsed data
        return cls(bootstrap_methods=parsed_methods)


# --- STEP 2: Monkey-Patch the discovery function to include our parser ---

_patch_applied = False

def apply_lawu_parser_patch():
    """
    Wraps lawu.attributes.get_attribute_classes to inject our custom parser.
    This is the cleanest way to extend the library at runtime.
    """
    global _patch_applied
    if _patch_applied:
        return

    logger.info("Applying runtime patch to lawu for BootstrapMethods attribute parsing.")

    # Get a reference to the original function
    original_get_attributes = attribute.get_attribute_classes

    # functools.wraps ensures we preserve the original function's metadata, like its lru_cache
    @functools.wraps(original_get_attributes)
    def wrapped_get_attributes() -> dict:
        # Call the original function to get all the built-in parsers
        result = original_get_attributes()
        
        # Add our custom parser to the dictionary
        # The key must be lowercase, just like the original function does
        if 'bootstrapmethods' not in result:
            result['bootstrapmethods'] = BootstrapMethodsAttribute

        return result

    # Replace the function in the lawu.attributes module with our wrapped version
    attribute.get_attribute_classes = wrapped_get_attributes
    _patch_applied = True


# --- STEP 3: Apply the patch and run your code ---

# Call this ONCE at the start of your script
apply_lawu_parser_patch()
