var linkFromList = 0; // this is a flag to go back to the list that called it.  0 = business name, 2 = officer name, 3 = registered agent

//***********************************************************************************//
//************************** JQUery Query String Extender ***************************//
//***********************************************************************************//
// MGS - Note to self - Refactor this and include in a file.
$.extend({
    getUrlVars: function () {
        var vars = [], hash;
        var href = decodeURI(window.location.href);
        var hashes = href.slice(href.indexOf('?') + 1).split('&');
        for (var i = 0; i < hashes.length; i++) {
            hash = hashes[i].split('=');
            vars.push(hash[0]);
            vars[hash[0]] = hash[1];
        }
        return vars;
    },
    getUrlVar: function (name) {
        return $.getUrlVars()[name];
    },
    clearQueryString: function () {
        // some of the older browsers dont support this
        //history.pushState({}, document.title, "?");

        // fall back for any browsers that dont support the pushstate
        //window.location.href = "#clear=1";

    }
});

//***********************************************************************************//
//********************************* On Page Load ************************************//
//***********************************************************************************//
var pos; // global
$(document).ready(function () {

    var onTabSelectChange = function (e) {
        ClearSearches();

        // access the selected item via e.item (Element)
    };

    // Kendo tabs
    var tabstrip = $("#tabstrip").kendoTabStrip({
        animation: {
            open: {
                duration: 20,
                effects: "fadeIn"
            }
        }
    });

    // Attach function to run on selection changed
    tabstrip.data("kendoTabStrip").bind("select", onTabSelectChange);

    ClearSearches();

    var searchBy = $.getUrlVar('searchby');

    if (searchBy == "officer") {
        var officerName = $.getUrlVar('officerName');
        tabstrip.data("kendoTabStrip").select(2);
        $("#officerNameTextBox").val(officerName);
        OfficerNameSearch();
    }
    else if (searchBy == "agent") {
        var agentName = $.getUrlVar('agentName');
        tabstrip.data("kendoTabStrip").select(3);
        $("#registeredAgentTextBox").val(agentName);

        AgentNameSearch();
    }

    // Clear the querystring without actually doing a postback.
    $.clearQueryString();

    $("#businessNameTextBox").keypress(function (e) {
        if (e.target.value.trim() !== "") {
            if ((e.which && e.which == 13) || (e.keyCode && e.keyCode == 13)) {
                BusinessNameSearch();
                return false;
            }
        }
        return true;
    });

    $("#businessNameSearchButton").click(function (e) {
        //console.log($('#businessNameTextBox').val());
        if ($('#businessNameTextBox').val().trim() !== "") {
            if (window.pageYOffset) {
                pos = window.pageYOffset;
            }
            if (document.body.scrollTop) {
                pos = document.body.scrollTop;
            }
            if (document.documentElement.scrollTop) {
                pos = document.documentElement.scrollTop;
            }
            BusinessNameSearch();
            return false;
        }
    });

    $("#businessIdTextBox").keypress(function (e) {
        if (e.target.value.trim() !== "") {
            if ((e.which && e.which == 13) || (e.keyCode && e.keyCode == 13)) {
                console.log(e);
                BusinessIdSearch();
                return false;
            }
        }
        return true;
    });

    $("#businessIdSearchButton").click(function (e) {
        if ($("#businessIdTextBox").val().trim() !== "") {
            BusinessIdSearch();
            return false;
        }
    });

    $("#officerNameTextBox").keypress(function (e) {
        if (e.target.value.trim() !== "") {
            if ((e.which && e.which == 13) || (e.keyCode && e.keyCode == 13)) {
                OfficerNameSearch();
                return false;
            }
        }
        return true;
    });

    $("#officerNameSearchButton").click(function (e) {
        if ($("#officerNameTextBox").val().trim() !== "") {
            OfficerNameSearch();
            return false;
        }
    });

    $("#registeredAgentTextBox").keypress(function (e) {
        if (e.target.value.trim() !== "") {
            if ((e.which && e.which == 13) || (e.keyCode && e.keyCode == 13)) {
                AgentNameSearch();
                return false;
            }
        }
        return true;
    });

    $("#registeredAgentNameSearchButton").click(function (e) {
        if ($("#registeredAgentTextBox").val().trim() !== "") {
            AgentNameSearch();
            return false;
        }
    });
});

//***********************************************************************************//
//******************************* Common Functions **********************************//
//***********************************************************************************//

function ClearSearches() {
    // clear searches
    $('#search-details').hide();

    $('#business-results').hide();
    $('#officer-results').hide();
    $('#business-id-results').hide();

    $('#modal-business-details').hide();

    $('#agent-results').hide();
    $('#businessIdTextBox').val('');
    $('#businessNameTextBox').val('');
    $('#officerNameTextBox').val('');
    $('#registeredAgentTextBox').val('');
}

function getServiceURL() {
    var siteURL = getSiteURL();

    //Meena - The URL to the webservice is different if the website is deployed to a virtual directory, Which is why I had to put in this HACK
    if (siteURL.indexOf("portal") !== -1) {
        siteURL = siteURL + '/../Services/MS/CorpServices.asmx';
    }
    else {
        siteURL = siteURL + '/Services/MS/CorpServices.asmx';
    }

    return siteURL
}

function getSiteURL() {
    pathArray = window.location.pathname.split('/');
    return window.location.protocol + "//" + window.location.host + "/" + pathArray[1];
}

function ShowSearchDetails(searchType, subType, criteria, count) {

    // set the criteria section
    $('#search-detail-type').text(searchType);
    $('#search-detail-subtype').text(subType);
    $('#search-detail-criteria').text(criteria);

    var strDate = new Date().format('MM/dd/yyyy hh:mm');
    $('#search-detail-date').text(strDate);
    $('#search-detail-count').text(count);
    $('#search-details').show();

    var thruDate = new Date();
    thruDate.setDate(thruDate.getDate() - 2);
    $('#search-detail-thrudate').text(thruDate.format('MM/dd/yyyy'));


    // go get search thru date
    //$.ajax({
    //    type: "POST",
    //    url: getServiceURL() + "/GetSearchThruDate",
    //    contentType: "application/json; charset=utf-8",
    //    dataType: "json",
    //    async: true,
    //    success: function (data) {
    //        // Render the resulting data, via template.
    //        var search = eval('(' + data.d + ')');
    //        var std = new Date(search);
    //        $('#search-detail-thrudate').text(std.format('MM/dd/yyyy'));
    //    }
    //});

}

function showModalBusinessDetails(filingId, title) {
    if ($("#modalwindow").data("kendoWindow")) {
        $("#modalwindow").data("kendoWindow").destroy();
    }

    $("#modal-business-details").append("<div id='modalwindow'></div>"); // Since we destroy the modal window on close - recreate the div.

    var urlToLoad = "ViewXSLTFileByName.aspx?providerName=MSBSD_CorporationBusinessDetails&FilingId=" + filingId;
	

			
		

    // Kendo Modal Window
    var modalWindow = $("#modalwindow").kendoWindow({
    	
		width: "750px",
        
        title: "Business Details",
        modal: true,
        visible: false,
        maximize: false,
        resizable: true,
        draggable: true,
        //content: urlToLoad,
        actions: ["Close"],
        close: function () { // Destroy the window every single time on close - not destroying it causes problems when tabs are changed. 
            this.destroy();
        },
        animation: {
            open: {
                duration: 20,
                effects: "fadeIn"
            },
            close: { // DONT REMOVE THIS - IT PREVENTS KENDO WINDOW from RANDOMLY transforming the CSS
                effects: "fadeIn",
                reverse: true
            }
        }
    }).data("kendoWindow");

    if (modalWindow) {
        
		$.get(urlToLoad, function(data){
			modalWindow.title(title);
			//modalWindow.refresh({ url: "~/ViewXSLTFileByName.aspx", data: { providerName: "MSBSD_CorporationBusinessDetails", FilingId: filingId } });
			modalWindow.content(data);
			modalWindow.open();
			modalWindow.center();
			
		});
		
    }
}

//***********************************************************************************//
//****************************** Business Name Search *******************************//
//***********************************************************************************//

function BusinessNameSearch() {

    var args = JSON.stringify({ SearchType: $('input:radio[name=searchBy]:checked').val(), BusinessName: $("#businessNameTextBox").val() });
    if ($("#businessSearchResultsDiv").kendoGrid) {
        $("#businessSearchResultsDiv").val('');
    }
    $.ajax({
        type: "POST",
        url: getServiceURL() + "/BusinessNameSearch",
        data: args,
        contentType: "application/json; charset=utf-8",
        dataType: "json",
        processdata: false,
        success: function (obj) {
            BindBusinessNameSearchGrid(obj);
        }
    });
}

function BindBusinessNameSearchGrid(obj) {

    var resultCount = 0;

    var dataTable = JSON.parse(obj.d).Table

    if (dataTable) {
        resultCount = dataTable.length;
    }

    var nameSearchResults = new kendo.data.DataSource({
        data: dataTable,
        page: 1,
        schema: {
            model: {
                id: "FilingId",
                fields: {
                    BusinessName: { type: "string" },
                    BusinessId: { type: "number" },
                    FilingtypeName: { type: "string" },
                    FilingStatus: { type: "string" },
                    BusinessFormedDate: { type: "date" },
                    FilingId: { type: "string" }
                }
            }
        },
        pageSize: 10

    });
    // $("#businessSearchResultsDiv").data("kendoGrid").dataSource.data([]);
    if ($("#businessSearchResultsDiv").data("kendoGrid")) {
        $("#businessSearchResultsDiv").data("kendoGrid").dataSource.data([]);
    }
    $("#businessSearchResultsDiv").kendoGrid({
        dataSource: nameSearchResults,
        filterable: true,
        scrollable: false,
        pageable: {
            refresh: true,
            previousNext: false,
            messages: {
                empty: "No Matches Found."
            }
        },
        sortable: {
            mode: "single",
            allowUnsort: false
        },
        columns: [{
            field: "BusinessName",
            title: "Business Name",
            filterable: false
        },
        {
            field: "BusinessId",
            title: "Business ID",
            filterable: false
        },
        {
            field: "FilingtypeName",
            title: "Type",
            filterable: true
        },
        {
            field: "FilingStatus",
            title: "Status",
            filterable: true
        },
        {
            field: "BusinessFormedDate",
            title: "Create Date",
            width: 120,
            format: "{0:MM/dd/yyyy}"
        },
        {
            command: [{
                text: "Details",
                click: ShowBusinessDetails,
                title: " ",
                width: 100

            }],
            dataBound: onDataBound,
        }
        ]
    });
    $("#pager").kendoPager({
        autoBind: false,
        dataSource: nameSearchResults
    });
    $('#business-results').show();

    ShowSearchDetails('Business Name', getBusinessNameSearchType(), $("#businessNameTextBox").val(), resultCount);
}
function onDataBound(e) {

    // this.content.scrollTop(this.tbody.height());

    // if(window.pageYOffset)
    // {
    //     pos = window.pageYOffset;
    // }
    // if(document.body.scrollTop)
    // {
    //     pos = document.body.scrollTop;
    // }
    // if(document.documentElement.scrollTop)
    // {
    //     pos = document.documentElement.scrollTop;
    // }

    // console.log(pos);
    // window.scrollTo(0, 108);

}

function fixGrid() {
    var count = $("#businessSearchResultsDiv").data("kendoGrid").dataSource.data().length;
    if (count <= 10) {
        $("#businessSearchResultsDiv .k-grid-content").removeAttr("style");
    }
}

function ShowBusinessDetails(e) {
    var grid = $("#businessSearchResultsDiv").data("kendoGrid");
    var dataItem = grid.dataItem($(e.currentTarget).closest("tr"));

    var title = dataItem["BusinessName"];
    var filingId = dataItem["FilingId"]
    showModalBusinessDetails(filingId, title);
    fixGrid();
}

function getBusinessNameSearchType() {
    var subType = '';

    switch ($('input:radio[name=searchBy]:checked').val()) {
        case 'startingwith': subType = 'Starting With'; break;
        case 'matchall': subType = 'All Words'; break;
        case 'matchany': subType = 'Any Words'; break;
        case 'soundslike': subType = 'Sounds Like'; break;
        case 'exact': subType = 'Exact Match'; break;
    }

    return subType;
}

//***********************************************************************************//
//****************************** Business Id Search *********************************//
//***********************************************************************************//

function BusinessIdSearch() {
    // Get value
    var businessId = $('#businessIdTextBox').val().trim();
    // Trim it and Set it
    $('#businessIdTextBox').val(businessId);
    // Search it
    var args = JSON.stringify({ BusinessId: businessId });

    $.ajax({
        type: "POST",
        url: getServiceURL() + "/BusinessIdSearch",
        data: args,
        contentType: "application/json; charset=utf-8",
        dataType: "json",
        processdata: false,
        success: function (obj) {
            BindBusinessIdSearchGrid(obj);
        }
    });

}

function BusinessIdSearch2(businessId) {
    $('#businessIdTextBox').val(businessId);
    // Search it
    var args = JSON.stringify({ BusinessId: businessId });

    $.ajax({
        type: "POST",
        url: getServiceURL() + "/BusinessIdSearch",
        data: args,
        contentType: "application/json; charset=utf-8",
        dataType: "json",
        processdata: false,
        success: function (obj) {
            BindBusinessIdSearchGrid(obj);
        }
    });
}


function BindBusinessIdSearchGrid(obj) {
    var resultCount = 0;

    var dataTable = JSON.parse(obj.d).Table

    if (dataTable) {
        resultCount = dataTable.length;
    }

    var searchResults = new kendo.data.DataSource({
        data: dataTable,
        schema: {
            model: {
                id: "FilingId",
                fields: {
                    BusinessId: { type: "number" },
                    EntityId: { type: "string" },
                    LegalName: { type: "string" },
                    FilingId: { type: "string" }
                }
            }
        },
        pageSize: 10

    });

    $("#businessIdSearchResultsDiv").kendoGrid({
        dataSource: searchResults,
        filterable: false,
        scrollable: false,
        pageable: {
            refresh: true
        },
        columns: [{
            field: "BusinessId",
            title: "Business ID",
            filterable: false
        },
        {
            field: "LegalName",
            title: "Business Name",
            filterable: true
        },
        {
            command: [{
                text: "Details",
                click: ShowBusinessIdDetails,
                title: " ",
                width: 100

            }]
        }
        ]
    });

    $('#business-id-results').show();

    ShowSearchDetails('Business ID', "", $("#businessIdTextBox").val(), resultCount);

    if ((dataTable) && (dataTable.length > 0)) {
        showModalBusinessDetails(dataTable[0]["FilingId"], dataTable[0]["LegalName"]);
    }
}

function ShowBusinessIdDetails(e) {
    var grid = $("#businessIdSearchResultsDiv").data("kendoGrid");
    var dataItem = grid.dataItem($(e.currentTarget).closest("tr"));

    var title = dataItem["LegalName"];
    var filingId = dataItem["FilingId"]
    showModalBusinessDetails(filingId, title, 'no');
}

//***********************************************************************************//
//******************************* Officer Name Search *******************************//
//***********************************************************************************//

function OfficerNameSearch() {

    var args = JSON.stringify({ OfficerName: $("#officerNameTextBox").val() });

    $.ajax({
        type: "POST",
        url: getServiceURL() + "/OfficerNameSearch",
        data: args,
        contentType: "application/json; charset=utf-8",
        dataType: "json",
        processdata: false,
        success: function (obj) {
            BindOfficerNameSearchGrid(obj);
        }
    });
}

function BindOfficerNameSearchGrid(obj) {
    var resultCount = 0;

    var dataTable = JSON.parse(obj.d).Table

    if (dataTable) {
        resultCount = dataTable.length;
    }

    var nameSearchResults = new kendo.data.DataSource({
        data: dataTable,
        schema: {
            model: {
                id: "FilingId",
                fields: {
                    OfficerName: { type: "string" },
                    Title: { type: "string" },
                    LegalName: { type: "string" },
                    FilingId: { type: "string" }
                }
            }
        },
        pageSize: 10

    });

    $("#officerSearchResultsDiv").kendoGrid({
        dataSource: nameSearchResults,
        filterable: true,
        scrollable: false,
        pageable: {
            refresh: true
        },
        sortable: {
            mode: "single",
            allowUnsort: false
        },
        columns: [{
            field: "OfficerName",
            title: "Officer Name",
            filterable: false
        },
         {
             field: "Title",
             title: "Title",
             filterable: false
         },
        {
            field: "LegalName",
            title: "Business Name",
            filterable: true
        },
        {
            command: [{
                text: "Details",
                click: ShowOfficerBusinessDetails,
                title: " ",
                width: 100

            }]
        }
        ]
    });

    $('#officer-results').show();

    ShowSearchDetails('Officer Name', "", $("#officerNameTextBox").val(), resultCount);
}

function ShowOfficerBusinessDetails(e) {
    var grid = $("#officerSearchResultsDiv").data("kendoGrid");
    var dataItem = grid.dataItem($(e.currentTarget).closest("tr"));

    var title = dataItem["LegalName"];
    var filingId = dataItem["FilingId"]
    showModalBusinessDetails(filingId, title);
}

//***********************************************************************************//
//*************************** Registered Agent Name Search **************************//
//***********************************************************************************//

function AgentNameSearch() {

    var args = JSON.stringify({ AgentName: $("#registeredAgentTextBox").val() });

    $.ajax({
        type: "POST",
        url: getServiceURL() + "/AgentNameSearch",
        data: args,
        contentType: "application/json; charset=utf-8",
        dataType: "json",
        processdata: false,
        success: function (obj) {
            BindAgentNameSearchGrid(obj);
        }
    });
}

function BindAgentNameSearchGrid(obj) {
    var resultCount = 0;

    var dataTable = JSON.parse(obj.d).Table

    if (dataTable) {
        resultCount = dataTable.length;
    }

    var nameSearchResults = new kendo.data.DataSource({
        data: dataTable,
        schema: {
            model: {
                id: "FilingId",
                fields: {
                    BusinessId: { type: "number" },
                    AgentName: { type: "string" },
                    LegalName: { type: "string" },
                    FilingId: { type: "string" }
                }
            }
        },
        pageSize: 10

    });

    $("#agentSearchResultsDiv").kendoGrid({
        dataSource: nameSearchResults,
        filterable: true,
        scrollable: false,
        pageable: {
            refresh: true
        },
        sortable: {
            mode: "single",
            allowUnsort: false
        },
        columns: [{
            field: "AgentName",
            title: "Agent Name",
            filterable: false
        },
        {
            field: "BusinessId",
            title: "Id",
            filterable: false
        },
        {
            field: "LegalName",
            title: "Business Name",
            filterable: true
        },
        {
            command: [{
                text: "Details",
                click: ShowAgentBusinessDetails,
                title: " ",
                width: 100

            }]
        }
        ]
    });

    $('#agent-results').show();

    ShowSearchDetails('Agent Name', "", $("#registeredAgentTextBox").val(), resultCount);
}

function ShowAgentBusinessDetails(e) {
    var grid = $("#agentSearchResultsDiv").data("kendoGrid");
    var dataItem = grid.dataItem($(e.currentTarget).closest("tr"));

    var title = dataItem["LegalName"];
    var filingId = dataItem["FilingId"]
    showModalBusinessDetails(filingId, title);
}