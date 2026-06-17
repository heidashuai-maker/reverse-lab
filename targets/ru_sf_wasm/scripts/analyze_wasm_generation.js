const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

function parseArgs(argv) {
    const args = {
        sourceDir: path.resolve(__dirname, "..", "source"),
        trace: path.resolve(__dirname, "..", "..", "..", "js_reverse_cache", "ru_sf_wasm_node_wasm_full_trace_current.json"),
        compareTrace: null,
        out: null,
    };
    for (let index = 2; index < argv.length; index += 1) {
        const item = argv[index];
        if (item === "--source-dir") {
            args.sourceDir = path.resolve(argv[++index]);
        } else if (item === "--trace") {
            args.trace = path.resolve(argv[++index]);
        } else if (item === "--compare-trace") {
            args.compareTrace = path.resolve(argv[++index]);
        } else if (item === "--out") {
            args.out = path.resolve(argv[++index]);
        }
    }
    return args;
}

function sha256(buffer) {
    return crypto.createHash("sha256").update(buffer).digest("hex");
}

class WasmReader {
    constructor(buffer, start = 0, end = buffer.length) {
        this.buffer = buffer;
        this.offset = start;
        this.end = end;
    }

    eof() {
        return this.offset >= this.end;
    }

    readU8() {
        if (this.offset >= this.end) throw new Error("unexpected wasm eof");
        return this.buffer[this.offset++];
    }

    readBytes(length) {
        if (this.offset + length > this.end) throw new Error("unexpected wasm eof");
        const value = this.buffer.subarray(this.offset, this.offset + length);
        this.offset += length;
        return value;
    }

    readVarU32() {
        let result = 0;
        let shift = 0;
        for (;;) {
            const byte = this.readU8();
            result |= (byte & 0x7f) << shift;
            if ((byte & 0x80) === 0) return result >>> 0;
            shift += 7;
            if (shift > 35) throw new Error("invalid wasm u32 leb");
        }
    }

    readVarI32() {
        let result = 0;
        let shift = 0;
        let byte = 0;
        do {
            byte = this.readU8();
            result |= (byte & 0x7f) << shift;
            shift += 7;
        } while (byte & 0x80);
        if (shift < 32 && (byte & 0x40)) {
            result |= (~0 << shift);
        }
        return result;
    }

    readName() {
        const length = this.readVarU32();
        return Buffer.from(this.readBytes(length)).toString("utf8");
    }
}

function skipLimits(reader) {
    const flags = reader.readVarU32();
    reader.readVarU32();
    if (flags & 0x01) reader.readVarU32();
}

function skipConstExpr(reader) {
    for (;;) {
        const opcode = reader.readU8();
        if (opcode === 0x0b) return;
        if (opcode === 0x41 || opcode === 0x42) reader.readVarI32();
        else if (opcode === 0x43) reader.readBytes(4);
        else if (opcode === 0x44) reader.readBytes(8);
        else if (opcode === 0x23 || opcode === 0xd2) reader.readVarU32();
        else if (opcode === 0xd0) reader.readVarI32();
    }
}

function skipBlockType(reader) {
    const byte = reader.readU8();
    if (byte === 0x40 || byte === 0x7f || byte === 0x7e || byte === 0x7d || byte === 0x7c || byte === 0x7b || byte === 0x70 || byte === 0x6f) {
        return;
    }
    reader.offset -= 1;
    reader.readVarI32();
}

function skipMemArg(reader) {
    reader.readVarU32();
    reader.readVarU32();
}

function parseInstructionCalls(bytes) {
    const reader = new WasmReader(bytes);
    const calls = [];
    const indirectCalls = [];
    const refFuncs = [];
    const errors = [];

    try {
        while (!reader.eof()) {
            const opcode = reader.readU8();
            if (opcode === 0x10) {
                calls.push(reader.readVarU32());
            } else if (opcode === 0x11) {
                indirectCalls.push({typeIndex: reader.readVarU32(), tableIndex: reader.readVarU32()});
            } else if (opcode === 0xd2) {
                refFuncs.push(reader.readVarU32());
            } else if (opcode >= 0x02 && opcode <= 0x04) {
                skipBlockType(reader);
            } else if (opcode === 0x0c || opcode === 0x0d || (opcode >= 0x20 && opcode <= 0x26)) {
                reader.readVarU32();
            } else if (opcode === 0x0e) {
                const count = reader.readVarU32();
                for (let index = 0; index < count + 1; index += 1) reader.readVarU32();
            } else if (opcode === 0x1c) {
                const count = reader.readVarU32();
                reader.readBytes(count);
            } else if (opcode >= 0x28 && opcode <= 0x3e) {
                skipMemArg(reader);
            } else if (opcode === 0x3f || opcode === 0x40) {
                reader.readU8();
            } else if (opcode === 0x41 || opcode === 0x42) {
                reader.readVarI32();
            } else if (opcode === 0x43) {
                reader.readBytes(4);
            } else if (opcode === 0x44) {
                reader.readBytes(8);
            } else if (opcode === 0xd0) {
                reader.readVarI32();
            } else if (opcode === 0xfc) {
                const subopcode = reader.readVarU32();
                if (subopcode === 8) {
                    reader.readVarU32();
                    reader.readVarU32();
                } else if (subopcode === 9 || subopcode === 11 || subopcode === 13 || subopcode === 15 || subopcode === 16 || subopcode === 17) {
                    reader.readVarU32();
                } else if (subopcode === 10 || subopcode === 12 || subopcode === 14) {
                    reader.readVarU32();
                    reader.readVarU32();
                }
            } else if (opcode === 0xfd) {
                const subopcode = reader.readVarU32();
                if ((subopcode >= 84 && subopcode <= 91) || (subopcode >= 92 && subopcode <= 99)) {
                    reader.readBytes(16);
                } else if (subopcode < 84) {
                    skipMemArg(reader);
                    if (
                        (subopcode >= 21 && subopcode <= 34) ||
                        subopcode === 84 ||
                        subopcode === 85 ||
                        subopcode === 86 ||
                        subopcode === 87
                    ) {
                        reader.readU8();
                    }
                } else if (subopcode >= 100 && subopcode <= 115) {
                    reader.readU8();
                }
            }
        }
    } catch (error) {
        errors.push({offset: reader.offset, message: error.message});
    }

    return {calls, indirectCalls, refFuncs, errors};
}

function parseNameSection(bytes) {
    const reader = new WasmReader(bytes);
    const names = {};
    while (!reader.eof()) {
        const subsectionId = reader.readU8();
        const subsectionSize = reader.readVarU32();
        const end = reader.offset + subsectionSize;
        if (subsectionId === 1) {
            const count = reader.readVarU32();
            for (let index = 0; index < count; index += 1) {
                names[reader.readVarU32()] = reader.readName();
            }
        }
        reader.offset = end;
    }
    return names;
}

function parseWasmBinary(buffer) {
    const reader = new WasmReader(buffer);
    const magic = Buffer.from(reader.readBytes(4)).toString("hex");
    const version = Buffer.from(reader.readBytes(4)).toString("hex");
    if (magic !== "0061736d") {
        throw new Error("not a wasm binary");
    }

    const info = {
        version,
        sections: [],
        typeCount: 0,
        imports: [],
        functionTypes: [],
        tablesCount: 0,
        memoriesCount: 0,
        globalsCount: 0,
        exports: [],
        startFunction: null,
        codeBodies: [],
        functionNames: {},
    };

    while (!reader.eof()) {
        const id = reader.readU8();
        const size = reader.readVarU32();
        const start = reader.offset;
        const end = start + size;
        const section = new WasmReader(buffer, start, end);
        info.sections.push({id, size, offset: start});

        if (id === 0) {
            const name = section.readName();
            if (name === "name") {
                Object.assign(info.functionNames, parseNameSection(buffer.subarray(section.offset, end)));
            }
        } else if (id === 1) {
            info.typeCount = section.readVarU32();
        } else if (id === 2) {
            const count = section.readVarU32();
            for (let index = 0; index < count; index += 1) {
                const module = section.readName();
                const name = section.readName();
                const kind = section.readU8();
                const item = {module, name, kind};
                if (kind === 0) item.typeIndex = section.readVarU32();
                else if (kind === 1) {
                    item.elementType = section.readU8();
                    skipLimits(section);
                } else if (kind === 2) skipLimits(section);
                else if (kind === 3) {
                    item.valueType = section.readU8();
                    item.mutable = section.readU8();
                }
                info.imports.push(item);
            }
        } else if (id === 3) {
            const count = section.readVarU32();
            for (let index = 0; index < count; index += 1) info.functionTypes.push(section.readVarU32());
        } else if (id === 4) {
            info.tablesCount = section.readVarU32();
        } else if (id === 5) {
            info.memoriesCount = section.readVarU32();
        } else if (id === 6) {
            const count = section.readVarU32();
            info.globalsCount = count;
            for (let index = 0; index < count; index += 1) {
                section.readU8();
                section.readU8();
                skipConstExpr(section);
            }
        } else if (id === 7) {
            const count = section.readVarU32();
            for (let index = 0; index < count; index += 1) {
                info.exports.push({name: section.readName(), kind: section.readU8(), index: section.readVarU32()});
            }
        } else if (id === 8) {
            info.startFunction = section.readVarU32();
        } else if (id === 10) {
            const count = section.readVarU32();
            for (let index = 0; index < count; index += 1) {
                const bodySize = section.readVarU32();
                const bodyStart = section.offset;
                const bodyEnd = bodyStart + bodySize;
                const body = new WasmReader(buffer, bodyStart, bodyEnd);
                const localGroupCount = body.readVarU32();
                const locals = [];
                for (let localIndex = 0; localIndex < localGroupCount; localIndex += 1) {
                    locals.push({count: body.readVarU32(), type: body.readU8()});
                }
                const instructionBytes = buffer.subarray(body.offset, bodyEnd);
                const functionIndex = info.imports.filter((item) => item.kind === 0).length + index;
                info.codeBodies.push({
                    functionIndex,
                    bodySize,
                    locals,
                    ...parseInstructionCalls(instructionBytes),
                });
                section.offset = bodyEnd;
            }
        }
        reader.offset = end;
    }

    const functionImports = info.imports.filter((item) => item.kind === 0);
    for (let index = 0; index < functionImports.length; index += 1) {
        functionImports[index].functionIndex = index;
        if (!info.functionNames[index]) info.functionNames[index] = `${functionImports[index].module}.${functionImports[index].name}`;
    }
    for (const item of info.exports) {
        if (item.kind === 0 && !info.functionNames[item.index]) info.functionNames[item.index] = item.name;
    }

    return info;
}

function summarizeCallGraph(binaryInfo) {
    const functionImports = binaryInfo.imports.filter((item) => item.kind === 0);
    const importByIndex = Object.fromEntries(functionImports.map((item) => [item.functionIndex, item]));
    const bodyByIndex = Object.fromEntries(binaryInfo.codeBodies.map((item) => [item.functionIndex, item]));
    const directImportCallCounts = {};
    const directInternalCallCounts = {};
    const directImportCallersByIndex = {};
    const internalEdgesByIndex = {};
    const reverseInternalEdgesByIndex = {};
    const parseErrors = [];
    for (const body of binaryInfo.codeBodies) {
        for (const error of body.errors) {
            parseErrors.push({functionIndex: body.functionIndex, ...error});
        }
        for (const target of body.calls) {
            const name = binaryInfo.functionNames[target] || `func#${target}`;
            if (target < functionImports.length) {
                directImportCallCounts[name] = (directImportCallCounts[name] || 0) + 1;
                directImportCallersByIndex[target] ||= {};
                directImportCallersByIndex[target][body.functionIndex] = (directImportCallersByIndex[target][body.functionIndex] || 0) + 1;
            } else {
                directInternalCallCounts[name] = (directInternalCallCounts[name] || 0) + 1;
                internalEdgesByIndex[body.functionIndex] ||= [];
                internalEdgesByIndex[body.functionIndex].push(target);
                reverseInternalEdgesByIndex[target] ||= [];
                reverseInternalEdgesByIndex[target].push(body.functionIndex);
            }
        }
    }

    function functionName(functionIndex) {
        return binaryInfo.functionNames[functionIndex] || `func#${functionIndex}`;
    }

    function reachableSetFrom(functionIndex) {
        const visited = new Set();
        const stack = [functionIndex];
        while (stack.length) {
            const current = stack.pop();
            if (visited.has(current)) continue;
            visited.add(current);
            const body = bodyByIndex[current];
            if (!body) continue;
            for (const target of body.calls) {
                if (target >= functionImports.length && !visited.has(target)) {
                    stack.push(target);
                }
            }
        }
        return visited;
    }

    function reachableFrom(functionIndex) {
        const visited = reachableSetFrom(functionIndex);
        const imports = {};
        for (const current of visited) {
            const body = bodyByIndex[current];
            if (!body) continue;
            for (const target of body.calls) {
                if (target < functionImports.length) {
                    const name = functionName(target);
                    imports[name] = (imports[name] || 0) + 1;
                }
            }
        }
        return {
            functionIndex,
            functionName: functionName(functionIndex),
            reachableDefinedFunctionCount: visited.size,
            reachableImportCallCounts: Object.fromEntries(Object.entries(imports).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))),
        };
    }

    function reverseReachableSetTo(functionIndex) {
        const visited = new Set();
        const stack = [functionIndex];
        while (stack.length) {
            const current = stack.pop();
            for (const predecessor of reverseInternalEdgesByIndex[current] || []) {
                if (visited.has(predecessor)) continue;
                visited.add(predecessor);
                stack.push(predecessor);
            }
        }
        return visited;
    }

    function isImportantImport(name) {
        return [
            /setcookie/,
            /hostname_Location/,
            /protocol_Location/,
            /user_agent_Navigator/,
            /getparser/,
            /getfirstmatch/,
            /testregexp/,
            /stringtonumber/,
            /number_get/,
            /functiontostring/,
            /resoverflow/,
            /accelerometerused/,
            /tpcanvas/,
            /query_Permissions/,
            /enumerate_devices/,
        ].some((pattern) => pattern.test(name));
    }

    const exportedFunctions = binaryInfo.exports.filter((item) => item.kind === 0);
    const exportedReachableSets = Object.fromEntries(exportedFunctions.map((item) => [item.name, reachableSetFrom(item.index)]));
    const startReachableSet = binaryInfo.startFunction == null ? null : reachableSetFrom(binaryInfo.startFunction);

    function summarizeImportCallers(importItem) {
        const callers = Object.entries(directImportCallersByIndex[importItem.functionIndex] || {})
            .map(([callerIndex, directCallCount]) => {
                const functionIndex = Number(callerIndex);
                return {
                    functionIndex,
                    functionName: functionName(functionIndex),
                    directCallCount,
                    reachedFromExports: exportedFunctions
                        .filter((item) => exportedReachableSets[item.name].has(functionIndex))
                        .map((item) => item.name),
                    reachedFromStart: startReachableSet ? startReachableSet.has(functionIndex) : false,
                    reverseReachableDefinedFunctionCount: reverseReachableSetTo(functionIndex).size,
                };
            })
            .sort((a, b) => b.directCallCount - a.directCallCount || a.functionIndex - b.functionIndex);
        return {
            importFunctionIndex: importItem.functionIndex,
            importName: `${importItem.module}.${importItem.name}`,
            category: classifyImport(importItem.name),
            directCallCount: callers.reduce((sum, item) => sum + item.directCallCount, 0),
            directCallerCount: callers.length,
            callers: callers.slice(0, 40),
        };
    }

    const importantImportCallers = {};
    for (const item of functionImports.filter((entry) => isImportantImport(entry.name))) {
        importantImportCallers[item.name] = summarizeImportCallers(item);
    }

    const indirectCallSites = binaryInfo.codeBodies
        .filter((item) => item.indirectCalls.length)
        .map((item) => ({
            functionIndex: item.functionIndex,
            functionName: functionName(item.functionIndex),
            indirectCallCount: item.indirectCalls.length,
            indirectCalls: item.indirectCalls.slice(0, 8),
            reachedFromExports: exportedFunctions
                .filter((entry) => exportedReachableSets[entry.name].has(item.functionIndex))
                .map((entry) => entry.name),
        }))
        .sort((a, b) => b.indirectCallCount - a.indirectCallCount || a.functionIndex - b.functionIndex);

    return {
        importedFunctionCount: functionImports.length,
        definedFunctionCount: binaryInfo.functionTypes.length,
        codeBodyCount: binaryInfo.codeBodies.length,
        directImportCallCounts: Object.fromEntries(Object.entries(directImportCallCounts).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))),
        directInternalCallCountsTop: Object.fromEntries(Object.entries(directInternalCallCounts).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 80)),
        importantImportCallers,
        indirectCallSitesTop: indirectCallSites.slice(0, 80),
        exportedReachability: Object.fromEntries(exportedFunctions.map((item) => [item.name, reachableFrom(item.index)])),
        startReachability: binaryInfo.startFunction == null ? null : reachableFrom(binaryInfo.startFunction),
        parseErrors: parseErrors.slice(0, 20),
        parseErrorCount: parseErrors.length,
        indirectCallCount: binaryInfo.codeBodies.reduce((sum, item) => sum + item.indirectCalls.length, 0),
        refFuncCount: binaryInfo.codeBodies.reduce((sum, item) => sum + item.refFuncs.length, 0),
    };
}

function classifyImport(name) {
    if (name.includes("setcookie")) return "cookie_sink";
    if (
        name.includes("resoverflow") ||
        name.includes("accelerometerused") ||
        name.includes("debugtool") ||
        name.includes("errorsgenerated") ||
        name.includes("detailchrome") ||
        name.includes("tpcanvas")
    ) {
        return "active_probe";
    }
    if (name.startsWith("__widl_")) return "webidl_env_read";
    if (name.startsWith("__wbindgen_")) return "wasm_bindgen_runtime";
    if (
        name.includes("getparser") ||
        name.includes("getfirstmatch") ||
        name.includes("stringtonumber") ||
        name.includes("testregexp")
    ) {
        return "ua_parser_or_regex";
    }
    if (
        name.includes("globalThis") ||
        name.includes("_self_") ||
        name.includes("_window_") ||
        name.includes("_global_")
    ) {
        return "global_object_access";
    }
    if (
        name.includes("_all_") ||
        name.includes("_then_") ||
        name.includes("_catch_") ||
        name.includes("_finally_") ||
        name.includes("_new_") ||
        name.includes("_push_") ||
        name.includes("_join_") ||
        name.includes("forEach") ||
        name.includes("getOwnProperty") ||
        name.includes("getPrototypeOf") ||
        name.includes("_keys_") ||
        name.includes("_values_") ||
        name.includes("_get_") ||
        name.includes("_set_") ||
        name.includes("_has_") ||
        name.includes("_apply_") ||
        name.includes("_call_") ||
        name.includes("instanceof_Object")
    ) {
        return "js_reflection_or_collections";
    }
    return "other";
}

function countBy(items, selector) {
    const counts = {};
    for (const item of items) {
        const key = selector(item);
        counts[key] = (counts[key] || 0) + 1;
    }
    return Object.fromEntries(Object.entries(counts).sort(([a], [b]) => a.localeCompare(b)));
}

function decodedStrings(entry) {
    const strings = [];
    for (const arg of entry.args || []) {
        for (const item of arg.decodedStrings || []) {
            strings.push(item.value);
        }
        if (arg.decodedCookie) {
            strings.push(arg.decodedCookie);
        }
    }
    if (entry.memory && entry.memory.outString) {
        strings.push(entry.memory.outString.value);
    }
    return strings;
}

function simplifyCall(entry) {
    const item = {
        seq: entry.seq,
        name: entry.name,
        category: classifyImport(entry.name),
    };
    const strings = decodedStrings(entry);
    if (strings.length) item.strings = strings;
    if (entry.memory && Object.prototype.hasOwnProperty.call(entry.memory, "value")) {
        item.numberValue = entry.memory.value;
    } else if (entry.memory && entry.memory.outString) {
        item.outString = entry.memory.outString.value;
    }
    if (entry.result) item.result = entry.result;
    return item;
}

function traceCalls(trace) {
    return (trace && trace.wasmImportTrace || []).filter((item) => item.phase === "call");
}

function heapEntries(trace) {
    return trace && trace.wasmHeapTrace || [];
}

function sequenceSha256(items) {
    return sha256(Buffer.from(items.join("\n"), "utf8"));
}

function traceSetCookie(trace) {
    const entry = traceCalls(trace).find((item) => item.name === "__wbg_setcookie_b04b7af29c82f976");
    if (!entry) return null;
    return decodedStrings(entry).find((item) => item.startsWith("wasm=")) || null;
}

function traceSetCookieEntries(trace, beforeCount = 16) {
    const calls = traceCalls(trace);
    return calls
        .map((entry, index) => ({entry, index}))
        .filter((item) => item.entry.name === "__wbg_setcookie_b04b7af29c82f976")
        .map(({entry, index}) => ({
            index,
            seq: entry.seq,
            decodedCookie: decodedStrings(entry).find((item) => item.startsWith("wasm=")) || null,
            documentCookieAfter: entry.documentCookieAfter,
            previousCalls: calls.slice(Math.max(0, index - beforeCount), index).map(simplifyCall),
        }));
}

function wasmStackFrames(stack) {
    const frames = [];
    for (const line of stack || []) {
        const match = String(line).match(/wasm-function\[(\d+)\]:(0x[0-9a-f]+)/i);
        if (match) {
            const functionIndex = Number(match[1]);
            frames.push({
                functionIndex,
                offset: match[2],
            });
        }
    }
    return frames;
}

function summarizeImportantImportStacks(trace) {
    return traceCalls(trace)
        .filter((entry) => entry.stack && entry.stack.length)
        .map((entry) => ({
            seq: entry.seq,
            name: entry.name,
            strings: decodedStrings(entry),
            outString: entry.memory && entry.memory.outString && entry.memory.outString.value,
            wasmFrames: wasmStackFrames(entry.stack),
            stackHead: entry.stack.slice(0, 8),
        }));
}

function uniqueFeatureNames(trace) {
    const names = [];
    const seen = new Set();
    for (const [key, value] of trace && trace.wasmTrace || []) {
        if (typeof value !== "string" || !value.includes(`"name":"${key}"`) || seen.has(key)) {
            continue;
        }
        seen.add(key);
        names.push(key);
    }
    return names;
}

function numberGets(trace) {
    return traceCalls(trace)
        .filter((item) => item.name === "__wbindgen_number_get")
        .map((item) => ({seq: item.seq, value: item.memory && item.memory.value}));
}

function firstSequenceDiff(leftItems, rightItems, selector) {
    const limit = Math.min(leftItems.length, rightItems.length);
    for (let index = 0; index < limit; index += 1) {
        if (selector(leftItems[index]) !== selector(rightItems[index])) {
            return index;
        }
    }
    return leftItems.length === rightItems.length ? -1 : limit;
}

function compareTracePair(left, right) {
    const leftCalls = traceCalls(left);
    const rightCalls = traceCalls(right);
    const leftHeap = heapEntries(left);
    const rightHeap = heapEntries(right);
    const firstImportNameDiff = firstSequenceDiff(leftCalls, rightCalls, (item) => item.name);
    const firstHeapPhaseDiff = firstSequenceDiff(leftHeap, rightHeap, (item) => item.phase);
    const leftNumbers = numberGets(left);
    const rightNumbers = numberGets(right);
    const numberGetDiffs = [];
    for (let index = 0; index < Math.min(leftNumbers.length, rightNumbers.length); index += 1) {
        if (!Object.is(leftNumbers[index].value, rightNumbers[index].value)) {
            numberGetDiffs.push({index, left: leftNumbers[index], right: rightNumbers[index]});
        }
    }
    return {
        cookies: {
            left: left.cookies,
            right: right.cookies,
        },
        setCookie: {
            left: traceSetCookie(left),
            right: traceSetCookie(right),
            equal: traceSetCookie(left) === traceSetCookie(right),
        },
        importCallCounts: {
            left: leftCalls.length,
            right: rightCalls.length,
        },
        importNameSequenceSha256: {
            left: sequenceSha256(leftCalls.map((item) => item.name)),
            right: sequenceSha256(rightCalls.map((item) => item.name)),
            equal: sequenceSha256(leftCalls.map((item) => item.name)) === sequenceSha256(rightCalls.map((item) => item.name)),
        },
        firstImportNameDiff,
        heapEventCounts: {
            left: leftHeap.length,
            right: rightHeap.length,
        },
        heapPhaseSequenceSha256: {
            left: sequenceSha256(leftHeap.map((item) => item.phase)),
            right: sequenceSha256(rightHeap.map((item) => item.phase)),
            equal: sequenceSha256(leftHeap.map((item) => item.phase)) === sequenceSha256(rightHeap.map((item) => item.phase)),
        },
        firstHeapPhaseDiff,
        featureNames: {
            left: uniqueFeatureNames(left),
            right: uniqueFeatureNames(right),
        },
        numberGetDiffs,
    };
}

function isRiskLabel(value) {
    return typeof value === "string" && /^(PHANTOM_|HEADCHR_|WEBDRIVER|SELENIUM_|CHR_|SEQUENTUM)/.test(value);
}

function summarizeHeapValue(value) {
    if (!value || typeof value !== "object") return value;
    const out = {
        type: value.type,
        constructorName: value.constructorName,
    };
    for (const key of ["name", "state", "kind", "length", "value"]) {
        if (Object.prototype.hasOwnProperty.call(value, key)) out[key] = value[key];
    }
    if (value.keys) out.keys = value.keys;
    if (value.preview) out.preview = value.preview;
    return out;
}

function summarizeHeapTrace(heapTrace) {
    const heap = heapTrace || [];
    const riskLabelDictionary = [];
    const seenRiskLabels = new Set();
    const promiseAll = [];
    const closureCalls = [];
    const arrayJoinResults = [];
    const seenArrayJoinResults = new Set();

    for (const entry of heap) {
        if (
            entry.phase === "reflect-set" &&
            entry.key &&
            entry.value &&
            entry.key.value === entry.value.value &&
            isRiskLabel(entry.key.value) &&
            !seenRiskLabels.has(entry.key.value)
        ) {
            seenRiskLabels.add(entry.key.value);
            riskLabelDictionary.push({
                seq: entry.seq,
                key: entry.key.value,
                targetHandle: entry.targetHandle,
                targetKeys: entry.target && entry.target.keys,
            });
        } else if (entry.phase === "promise-all") {
            promiseAll.push({
                seq: entry.seq,
                arrayHandle: entry.arrayHandle,
                length: entry.array && entry.array.length,
            });
        } else if (entry.phase === "closure-call") {
            closureCalls.push({
                seq: entry.seq,
                kind: entry.kind,
                args: (entry.args || []).map(summarizeHeapValue),
            });
        } else if (entry.phase === "array-join" && typeof entry.result === "string") {
            const key = `${entry.separator}\u0000${entry.result}`;
            if (!seenArrayJoinResults.has(key)) {
                seenArrayJoinResults.add(key);
                arrayJoinResults.push({
                    seq: entry.seq,
                    separator: entry.separator,
                    resultLength: entry.result.length,
                    result: entry.result.length > 500 ? `${entry.result.slice(0, 500)}...` : entry.result,
                    arrayLength: entry.array && entry.array.length,
                });
            }
        }
    }

    return {
        count: heap.length,
        phaseCounts: countBy(heap, (item) => item.phase || "unknown"),
        riskLabelDictionary,
        riskLabelCount: riskLabelDictionary.length,
        promiseAll,
        arrayJoinResultCount: arrayJoinResults.length,
        arrayJoinResults: arrayJoinResults.slice(0, 80),
        closureCallCount: closureCalls.length,
        closureCallKinds: countBy(closureCalls, (item) => item.kind || "unknown"),
        closureCallSamples: closureCalls.slice(-16),
        terminalEvents: heap.slice(-12).map((item) => ({
            phase: item.phase,
            seq: item.seq,
            handle: item.handle,
            value: summarizeHeapValue(item.value),
        })),
    };
}

function parseObjectDebugString(value) {
    if (typeof value !== "string") return null;
    const match = value.match(/\{.*\}$/);
    if (!match) return null;
    try {
        return JSON.parse(match[0]);
    } catch {
        return null;
    }
}

function summarizeWasmTrace(wasmTrace) {
    const featureObjects = {};
    const scalarSignals = {};
    for (const [key, value] of wasmTrace || []) {
        const parsed = parseObjectDebugString(value);
        if (parsed && parsed.name && key === parsed.name) {
            featureObjects[key] = {
                consistent: parsed.consistent,
                dataKeys: parsed.data && typeof parsed.data === "object" ? Object.keys(parsed.data) : [],
                data: parsed.data,
            };
        } else if (!Object.prototype.hasOwnProperty.call(scalarSignals, key)) {
            scalarSignals[key] = value;
        }
    }
    return {
        count: (wasmTrace || []).length,
        scalarSignals,
        featureObjects,
        featureObjectCount: Object.keys(featureObjects).length,
        featureObjectNames: Object.keys(featureObjects),
    };
}

function extractAsciiStrings(buffer) {
    const text = buffer.toString("latin1");
    const matches = text.match(/[ -~]{4,}/g) || [];
    const unique = [...new Set(matches)];
    const interesting = unique.filter((item) =>
        /PHANTOM|HEADCHR|WEBDRIVER|SELENIUM|CHR_|wasm|max-age|arbitr|cookie|navigator|plugins|mimeTypes|screen|canvas|WebGL|permissions|mediaDevices/i.test(item)
    );
    return {
        uniqueCount: unique.length,
        interesting: interesting.slice(0, 300),
    };
}

function main() {
    const args = parseArgs(process.argv);
    const wasmJsPath = path.join(args.sourceDir, "wasm.js");
    const wasmPath = path.join(args.sourceDir, "wasm_bg.wasm");
    const wasmJs = fs.readFileSync(wasmJsPath, "utf8");
    const wasmBytes = fs.readFileSync(wasmPath);
    const module = new WebAssembly.Module(wasmBytes);
    const imports = WebAssembly.Module.imports(module);
    const exports = WebAssembly.Module.exports(module);
    const binaryInfo = parseWasmBinary(wasmBytes);
    const trace = fs.existsSync(args.trace) ? JSON.parse(fs.readFileSync(args.trace, "utf8")) : null;
    const compareTrace = args.compareTrace && fs.existsSync(args.compareTrace)
        ? JSON.parse(fs.readFileSync(args.compareTrace, "utf8"))
        : null;
    const calls = traceCalls(trace);
    const setCookieIndex = calls.findIndex((item) => item.name === "__wbg_setcookie_b04b7af29c82f976");
    const setCookie = setCookieIndex >= 0 ? calls[setCookieIndex] : null;
    const importCategories = countBy(imports, (item) => classifyImport(item.name));
    const callCategories = countBy(calls, (item) => classifyImport(item.name));
    const summary = {
        generatedAt: new Date().toISOString(),
        source: {
            wasmJsPath,
            wasmPath,
            wasmJsBytes: Buffer.byteLength(wasmJs),
            wasmBytes: wasmBytes.length,
            wasmJsSha256: sha256(Buffer.from(wasmJs)),
            wasmSha256: sha256(wasmBytes),
        },
        module: {
            importsCount: imports.length,
            exportsCount: exports.length,
            imports,
            exports,
            importCategories,
        },
        binary: {
            version: binaryInfo.version,
            sections: binaryInfo.sections,
            typeCount: binaryInfo.typeCount,
            tablesCount: binaryInfo.tablesCount,
            memoriesCount: binaryInfo.memoriesCount,
            globalsCount: binaryInfo.globalsCount,
            startFunction: binaryInfo.startFunction,
            namedFunctionCount: Object.keys(binaryInfo.functionNames).length,
            callGraph: summarizeCallGraph(binaryInfo),
        },
        wrapper: {
            hasWasmBindgenHeap: /new Array\(32\)/.test(wasmJs),
            hasSetCookieImport: wasmJs.includes("__wbg_setcookie_b04b7af29c82f976"),
            hasDefaultLoader: /n\.default=function/.test(wasmJs),
            hasMainExportWrapper: /n\.main=function/.test(wasmJs),
        },
        staticStrings: extractAsciiStrings(wasmBytes),
        trace: trace ? {
            tracePath: args.trace,
            cookies: trace.cookies,
            wasmTrace: summarizeWasmTrace(trace.wasmTrace),
            wasmImportTraceCount: (trace.wasmImportTrace || []).length,
            importCallCount: calls.length,
            importCallCategories: callCategories,
            heapTrace: summarizeHeapTrace(trace.wasmHeapTrace),
            importantImportStacks: summarizeImportantImportStacks(trace),
            setCookie: setCookie ? {
                index: setCookieIndex,
                seq: setCookie.seq,
                decodedCookie: decodedStrings(setCookie).find((item) => item.startsWith("wasm=")),
                documentCookieAfter: setCookie.documentCookieAfter,
                previousCalls: calls.slice(Math.max(0, setCookieIndex - 16), setCookieIndex).map(simplifyCall),
            } : null,
            setCookies: traceSetCookieEntries(trace),
        } : null,
        traceComparison: trace && compareTrace ? {
            leftTracePath: args.trace,
            rightTracePath: args.compareTrace,
            ...compareTracePair(trace, compareTrace),
        } : null,
    };

    const output = JSON.stringify(summary, null, 2);
    if (args.out) {
        fs.mkdirSync(path.dirname(args.out), {recursive: true});
        fs.writeFileSync(args.out, output + "\n", "utf8");
    }
    console.log(output);
}

main();
