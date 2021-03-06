from cft_namehandler import NameHandler, get_value_returned_type, get_local_name, get_abs_composed_name
from parsemod.cft_name import is_name, is_kw, compose_name
from parsemod.cft_syntaxtree_values import str_type
from parsemod.cft_others import extract_tokens
from cft_errors_handler import ErrorsHandler
from compile.cft_compile import get_num_type
from py_utils import isnotfinished
from lexermod.cft_token import *
import parsemod.cft_ops as ops
from copy import deepcopy


def _is_type_expression(
        tokens: list[Token] | Token,
        errors_handler: ErrorsHandler,
        path: str,
        namehandler: NameHandler,
        i: int = 0
) -> bool:
    tokens = extract_tokens(tokens, i)

    if tokens is None:
        return False

    if is_name(tokens, errors_handler, path, namehandler, debug_info=_is_type_expression.__name__):
        composed_name = compose_name(tokens)
        if namehandler.has_globalname(composed_name):
            if namehandler.isinstance(composed_name, '$struct'):
                return True

            errors_handler.final_push_segment(
                path,
                f'TypeError: name `{get_local_name(composed_name)}` is not a type',
                tokens[-1],
                fill=True
            )

        errors_handler.final_push_segment(
            path,
            f'NameError: name `{get_local_name(composed_name)}` is not defined',
            tokens[-1],
            fill=True
        )
        return False

    errors_handler.final_push_segment(
        path,
        f'SyntaxError: invalid syntax',
        tokens[-1],
        fill=True
    )

    return False


def _is_name_call_expression(
        tokens: list[Token] | Token,
        errors_handler: ErrorsHandler,
        path: str,
        namehandler: NameHandler,
        i: int = 0,
        without_tail=False  # if True tokens after call name expression are not taken into account
):
    tokens = tokens[i:]

    parenthesis_index = -1

    for k in range(len(tokens)):
        if tokens[k].type == TokenTypes.PARENTHESIS:
            parenthesis_index = k
            break

    if parenthesis_index == -1 or not is_name(
            tokens[:parenthesis_index], errors_handler, path, namehandler, debug_info=_is_name_call_expression.__name__
    ) or (
            without_tail and len(tokens) > (parenthesis_index + 1)
    ):
        return False

    return True


def _is_value_expression(
        tokens: list[Token] | Token,
        errors_handler: ErrorsHandler,
        path: str,
        namehandler: NameHandler,
        i: int = 0
) -> bool:
    """<expr>"""
    tokens = extract_tokens(tokens, i)

    if tokens is None:
        return False

    if len(tokens) == 1:
        if tokens[0].type in (TokenTypes.NUMBER, TokenTypes.STRING) or is_name(
                tokens[0], errors_handler, path, namehandler, debug_info=_is_value_expression.__name__
        ) or is_kw(tokens[0], ('True', 'False')):
            return True

        if tokens[0].type == TokenTypes.TUPLE:
            for item in tokens[0].value:
                if not _is_value_expression(item, errors_handler, path, namehandler):
                    return False
            return True

        if tokens[0].type in (TokenTypes.PARENTHESIS, TokenTypes.SQUARE_BRACKETS, TokenTypes.CURLY_BRACES):
            return not tokens[0].value or _is_value_expression(tokens[0].value, errors_handler, path, namehandler)
    elif ops.is_op(tokens[0], source=ops.LOPS) and _is_value_expression(tokens, errors_handler, path, namehandler, 1):
        # LOPS check

        return True
    else:
        iop = -1

        for k in range(len(tokens)):
            if ops.is_op(tokens[k], source=ops.MIDDLE_OPS):
                iop = k
                break

        if iop != -1:
            if (_is_name_call_expression(
                    tokens[:iop], errors_handler, path, namehandler, without_tail=True
            ) or _is_value_expression(
                tokens[:iop], errors_handler, path, namehandler
            )) and _is_value_expression(tokens, errors_handler, path, namehandler, iop + 1):
                return True
        elif _is_name_call_expression(tokens, errors_handler, path, namehandler, without_tail=True):
            # calling name expression check

            return True

    return False


def _generate_name_call_expression(
        tokens: list[Token] | Token,
        errors_handler: ErrorsHandler,
        path: str,
        namehandler: NameHandler
):
    parenthesis_index = 1

    while parenthesis_index < len(tokens):
        if tokens[parenthesis_index].type == TokenTypes.PARENTHESIS:
            break

        parenthesis_index += 1

    name = compose_name(tokens[:parenthesis_index])

    if not namehandler.isinstance(name, ('fn', '$struct')):
        errors_handler.final_push_segment(
            path,
            f'NameError: name `{get_local_name(name)}` is not a function or structure',
            tokens[parenthesis_index - 1],
            fill=True
        )

        return {}

    args_tokens = []

    if tokens[parenthesis_index].value:
        if tokens[parenthesis_index].value[0].type == TokenTypes.TUPLE:
            args_tokens = tokens[parenthesis_index].value[0].value

            if not args_tokens[-1]:
                del args_tokens[-1]
        else:
            args_tokens = [tokens[parenthesis_index].value]

    namehandler_obj = deepcopy(namehandler.get_current_body(name))

    if namehandler_obj['type'] == '$struct':
        args_dict = namehandler_obj['value']
        expected_kwargs = list(args_dict.keys())
        max_args = positional_args = len(expected_kwargs)
        returned_type = get_abs_composed_name(namehandler_obj)
    else:
        args_dict = namehandler_obj['args']
        expected_kwargs = list(args_dict.keys())
        max_args = namehandler_obj['max-args']
        positional_args = namehandler_obj['positional-args']
        returned_type = namehandler_obj['returned-type']

    required_positional_args = len(args_tokens)

    if required_positional_args > max_args:
        errors_handler.final_push_segment(
            path,
            f'TypeError: {get_local_name(name)}() takes {max_args} positional arguments '
            f'but {required_positional_args} was given',
            tokens[parenthesis_index],
            fill=True
        )

        return {}

    if required_positional_args < positional_args:
        missing = positional_args - required_positional_args
        missed_args = expected_kwargs[required_positional_args: positional_args]
        error_tail = f'`{missed_args[-1]}`'

        if missing > 1:
            error_tail = f'`{missed_args[-2]}` and ' + error_tail

            if missing > 2:
                for missed_arg in missed_args[:-2][::-1]:
                    error_tail = f'`{missed_arg}`, ' + error_tail

        error_tail = ('' if missing == 1 else 's') + ': ' + error_tail

        errors_handler.final_push_segment(
            path,
            f'TypeError: {get_local_name(name)}() missing {missing} required positional argument' + error_tail,
            tokens[parenthesis_index],
            fill=True
        )

        return {}

    args = []
    for i in range(len(args_tokens)):
        arg_tokens = args_tokens[i]

        if not arg_tokens:
            break

        arg = _generate_expression_syntax_object(arg_tokens, errors_handler, path, namehandler)

        if errors_handler.has_errors():
            return {}

        del arg['$tokens-len']

        expected_type = args_dict[expected_kwargs[i]]
        expected_type = expected_type['type'] if expected_type['value'] is None \
            else get_value_returned_type(expected_type['value'])

        if arg['returned-type'] != '$undefined' and get_value_returned_type(arg) != expected_type:
            errors_handler.final_push_segment(
                path,
                f'TypeError: expected type `{expected_type}`, got `{get_value_returned_type(arg)}`',
                arg_tokens[0],
                fill=True
            )

        args.append(arg)

    if namehandler_obj['type'] == '$struct':
        fields = namehandler_obj['value']

        k = 0
        for key in fields:
            fields[key]['value'] = args[k]
            del fields[key]['*parent']
            k += 1

        return {
            'type': '$init-cls',
            'called-name': name,
            'fields': fields,
            'returned-type': returned_type,
            '$has-effect': True,
            '$constant-expr': False
        }
    else:
        return {
            'type': '$call-name',
            'called-name': name,
            'args': args,
            'returned-type': returned_type,
            '$has-effect': True,  # temp value
            '$constant-expr': False  # temp value
        }


def _generate_expression_syntax_object(
        tokens: list[Token] | Token,
        errors_handler: ErrorsHandler,
        path: str,
        namehandler: NameHandler,
        i: int = 0,
        right_i: int = 0,
        expected_type: dict | str = ...,
        effect_checker=False
):
    tokens = extract_tokens(tokens, i)
    tokens = tokens[:len(tokens) - right_i]

    res = {
        '$tokens-len': len(tokens),  # temp value
        '$has-effect': False,  # temp value,
        '$constant-expr': True  # temp value
    }

    if len(tokens) == 1:
        res['returned-type'] = '$self'  # it is necessary to refer to key 'type'

        token = tokens[0]

        if token.type == TokenTypes.STRING:
            # includes strings like `'Hello World'` or `"Hello World"`, and chars like `c'H'` or `c"H"`

            _index = token.value.index(token.value[-1])

            res.update({
                # `c` is prefix before quotes that's means is char, not string
                'type': str_type if 'c' not in token.value[:_index].lower() else ['$', 'char'],
                'value': token.value[_index + 1:-1]
            })
        elif token.type == TokenTypes.NUMBER:
            # includes any number format like integer or decimal

            res.update({
                'type': ['$', get_num_type(token.value)],
                'value': token.value
            })
        elif token.type == TokenTypes.NAME:
            res['value'] = token.value

            if token.value in ('True', 'False'):
                res['type'] = ['$', 'bool']
            elif not namehandler.has_globalname(token.value):
                errors_handler.final_push_segment(
                    path,
                    f'NameError: name `{token.value}` is not defined',
                    tokens[0],
                    fill=True
                )

                return {}
            else:
                res.update({
                    'type': 'name',
                    '$constant-expr': False
                })

                _obj = namehandler.get_current_body(token.value)

                if namehandler.isinstance(token.value, 'fn'):
                    res['returned-type'] = _obj['returned-type']
                else:
                    res['returned-type'] = _obj['type']
        elif token.type == TokenTypes.TUPLE:
            # <expression>, <expression>
            isnotfinished()

            res.update({
                'type': 'tuple',
                'value': []
            })

            for item in token.value:
                res['value'].append(_generate_expression_syntax_object(item, errors_handler, path, namehandler))

                del res['value'][-1]['$tokens-len']
        elif token.type in (TokenTypes.PARENTHESIS, TokenTypes.SQUARE_BRACKETS, TokenTypes.CURLY_BRACES):
            isnotfinished()

            if not token.value:
                res.update({
                    'type': {
                        TokenTypes.PARENTHESIS: 'tuple',
                        TokenTypes.SQUARE_BRACKETS: 'list',
                        TokenTypes.CURLY_BRACES: 'dict'
                    }[token.type],
                    'value': []
                })
            else:
                res = _generate_expression_syntax_object(token.value, errors_handler, path, namehandler)

                if token.type != TokenTypes.PARENTHESIS:
                    res['type'] = 'list' if token.type == TokenTypes.SQUARE_BRACKETS else 'set'

                    if res['type'] != 'tuple':
                        res['value'] = [res['value']]
    elif _is_name_call_expression(tokens, errors_handler, path, namehandler, without_tail=True):
        res.update(
            _generate_name_call_expression(tokens, errors_handler, path, namehandler)
        )
    else:
        res.update(ops.generate_op_expression(
            tokens,
            errors_handler,
            path,
            namehandler,
            _generate_expression_syntax_object,
            _is_name_call_expression,
            _generate_name_call_expression
        ))

    if errors_handler.has_errors():
        return {}

    if get_value_returned_type(res) == '$undefined':
        errors_handler.final_push_segment(
            path,
            'unpredictable behavior (it is impossible to calculate the return type)',
            tokens[0],
            type=ErrorsHandler.WARNING
        )
    elif expected_type is not ... and get_value_returned_type(res) != expected_type:
        errors_handler.final_push_segment(
            path,
            f'TypeError: expected type `{expected_type}`, got `{get_value_returned_type(res)}`',
            tokens[0],
            fill=True
        )
        return {}

    if not effect_checker:
        del res['$has-effect']

    return res


__all__ = (
    '_is_value_expression',
    '_generate_expression_syntax_object',
    '_is_type_expression'
)
