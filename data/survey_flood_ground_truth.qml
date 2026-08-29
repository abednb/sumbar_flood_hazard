<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34.0" styleCategories="AllStyleCategories">
  <renderer-v2 type="singleSymbol" symbollevels="0">
    <symbols>
      <symbol type="marker" name="0" alpha="1" clip_to_extent="1">
        <layer pass="0" class="SimpleMarker" locked="0">
          <prop k="angle" v="0"/>
          <prop k="color" v="227,26,28,255"/>
          <prop k="horizontal_anchor_point" v="1"/>
          <prop k="joinstyle" v="bevel"/>
          <prop k="name" v="circle"/>
          <prop k="offset" v="0,0"/>
          <prop k="outline_color" v="255,255,255,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0.6"/>
          <prop k="size" v="4"/>
          <prop k="vertical_anchor_point" v="1"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
  <fieldConfiguration>
    <field name="id">
      <editWidget type="Hidden"/>
    </field>
    <field name="surveyor_id">
      <editWidget type="TextEdit">
        <config>
          <Option type="Map">
            <Option type="QString" name="Placeholder" value="e.g., Surveyor 1"/>
          </Option>
        </config>
      </editWidget>
    </field>
    <field name="event_date">
      <editWidget type="DateTime">
        <config>
          <Option type="Map">
            <Option type="bool" name="allow_null" value="false"/>
            <Option type="QString" name="display_format" value="yyyy-MM-dd"/>
            <Option type="QString" name="field_format" value="yyyy-MM-dd"/>
          </Option>
        </config>
      </editWidget>
    </field>
    <field name="hwm_type">
      <editWidget type="ValueMap">
        <config>
          <Option type="Map">
            <Option type="List" name="map">
              <Option type="Map"><Option type="QString" name="Mudline on wall / pillar" value="Mudline on wall / pillar"/></Option>
              <Option type="Map"><Option type="QString" name="Debris caught on fence / tree" value="Debris caught on fence / tree"/></Option>
              <Option type="Map"><Option type="QString" name="Water stain on building interior" value="Water stain on building interior"/></Option>
              <Option type="Map"><Option type="QString" name="Eye-witness memory only" value="Eye-witness memory only"/></Option>
            </Option>
          </Option>
        </config>
      </editWidget>
    </field>
    <field name="water_depth_cm">
      <editWidget type="Range">
        <config>
          <Option type="Map">
            <Option type="double" name="Min" value="0"/>
            <Option type="double" name="Max" value="1000"/>
            <Option type="double" name="Step" value="1"/>
            <Option type="QString" name="Suffix" value=" cm"/>
          </Option>
        </config>
      </editWidget>
    </field>
    <field name="ground_ref_type">
      <editWidget type="ValueMap">
        <config>
          <Option type="Map">
            <Option type="List" name="map">
              <Option type="Map"><Option type="QString" name="Natural Ground / Road Surface" value="Natural Ground / Road Surface"/></Option>
              <Option type="Map"><Option type="QString" name="Elevated Building Floor" value="Elevated Building Floor"/></Option>
            </Option>
          </Option>
        </config>
      </editWidget>
    </field>
    <field name="floor_elevation_cm">
      <editWidget type="Range">
        <config>
          <Option type="Map">
            <Option type="double" name="Min" value="0"/>
            <Option type="double" name="Max" value="500"/>
            <Option type="double" name="Step" value="1"/>
            <Option type="QString" name="Suffix" value=" cm"/>
          </Option>
        </config>
      </editWidget>
    </field>
    <field name="peak_time">
      <editWidget type="TextEdit">
        <config>
          <Option type="Map">
            <Option type="QString" name="Placeholder" value="HH:MM (e.g. 15:30)"/>
          </Option>
        </config>
      </editWidget>
    </field>
    <field name="flood_duration_hrs">
      <editWidget type="Range">
        <config>
          <Option type="Map">
            <Option type="double" name="Min" value="0"/>
            <Option type="double" name="Max" value="168"/>
            <Option type="double" name="Step" value="0.5"/>
            <Option type="QString" name="Suffix" value=" hours"/>
          </Option>
        </config>
      </editWidget>
    </field>
    <field name="flow_source">
      <editWidget type="ValueMap">
        <config>
          <Option type="Map">
            <Option type="List" name="map">
              <Option type="Map"><Option type="QString" name="River Bank Overtopping (Fluvial)" value="River Bank Overtopping (Fluvial)"/></Option>
              <Option type="Map"><Option type="QString" name="Local Heavy Rainfall / Runoff (Pluvial)" value="Local Heavy Rainfall / Runoff (Pluvial)"/></Option>
              <Option type="Map"><Option type="QString" name="Tidal / Coastal Backwater" value="Tidal / Coastal Backwater"/></Option>
              <Option type="Map"><Option type="QString" name="Clogged Bridge / Culvert Drainage" value="Clogged Bridge / Culvert Drainage"/></Option>
            </Option>
          </Option>
        </config>
      </editWidget>
    </field>
    <field name="land_cover_ground">
      <editWidget type="ValueMap">
        <config>
          <Option type="Map">
            <Option type="List" name="map">
              <Option type="Map"><Option type="QString" name="Dense Settlement / Paved Concrete" value="Dense Settlement / Paved Concrete"/></Option>
              <Option type="Map"><Option type="QString" name="Paddy Field / Agriculture" value="Paddy Field / Agriculture"/></Option>
              <Option type="Map"><Option type="QString" name="Shrub / Bare Soil" value="Shrub / Bare Soil"/></Option>
              <Option type="Map"><Option type="QString" name="Riparian / Dense Forest" value="Riparian / Dense Forest"/></Option>
            </Option>
          </Option>
        </config>
      </editWidget>
    </field>
    <field name="flow_velocity_est">
      <editWidget type="ValueMap">
        <config>
          <Option type="Map">
            <Option type="List" name="map">
              <Option type="Map"><Option type="QString" name="Stagnant or Standing (under 0.2 m/s)" value="Stagnant or Standing (under 0.2 m/s)"/></Option>
              <Option type="Map"><Option type="QString" name="Moderate Flow (0.2 to 1.0 m/s)" value="Moderate Flow (0.2 to 1.0 m/s)"/></Option>
              <Option type="Map"><Option type="QString" name="Strong Current or Debris Flow (over 1.0 m/s)" value="Strong Current or Debris Flow (over 1.0 m/s)"/></Option>
            </Option>
          </Option>
        </config>
      </editWidget>
    </field>
    <field name="photo_hwm">
      <editWidget type="Attachment">
        <config>
          <Option type="Map">
            <Option type="QString" name="DefaultRoot" value="@project_folder + '/DCIM'"/>
            <Option type="QString" name="DocumentViewer" value="Image"/>
            <Option type="int" name="DocumentViewerHeight" value="250"/>
            <Option type="int" name="DocumentViewerWidth" value="250"/>
            <Option type="QString" name="FileWidget" value="true"/>
            <Option type="QString" name="FileWidgetFilter" value="Images (*.jpg *.jpeg *.png *.JPG *.JPEG *.PNG)"/>
            <Option type="QString" name="RelativeStorage" value="Relative2Project"/>
            <Option type="int" name="StorageMode" value="0"/>
          </Option>
        </config>
      </editWidget>
    </field>
    <field name="interviewee_name_role">
      <editWidget type="TextEdit">
        <config>
          <Option type="Map">
            <Option type="QString" name="Placeholder" value="Name and relation (e.g., Bpk. Budi - Resident)"/>
          </Option>
        </config>
      </editWidget>
    </field>
    <field name="notes">
      <editWidget type="TextEdit">
        <config>
          <Option type="Map">
            <Option type="bool" name="IsMultiline" value="true"/>
            <Option type="QString" name="Placeholder" value="Additional observations, flood marks on adjacent structures, etc."/>
          </Option>
        </config>
      </editWidget>
    </field>
  </fieldConfiguration>
  <aliases>
    <alias field="surveyor_id" name="Surveyor Name / ID" index="1"/>
    <alias field="event_date" name="Flood Event Date" index="2"/>
    <alias field="hwm_type" name="High-Water Mark (HWM) Type" index="3"/>
    <alias field="water_depth_cm" name="Observed Flood Depth (cm)" index="4"/>
    <alias field="ground_ref_type" name="Ground Reference Datum" index="5"/>
    <alias field="floor_elevation_cm" name="Floor Height above Ground (cm)" index="6"/>
    <alias field="peak_time" name="Time of Peak Inundation" index="7"/>
    <alias field="flood_duration_hrs" name="Total Inundation Duration (hrs)" index="8"/>
    <alias field="flow_source" name="Flood Water Origin / Mechanism" index="9"/>
    <alias field="land_cover_ground" name="Ground Land Cover (Manning n)" index="10"/>
    <alias field="flow_velocity_est" name="Estimated Flow Velocity" index="11"/>
    <alias field="photo_hwm" name="Photo of Mudline / Measuring Tape" index="12"/>
    <alias field="interviewee_name_role" name="Respondent Name and Role" index="13"/>
    <alias field="notes" name="Surveyor Notes and Observations" index="14"/>
  </aliases>
</qgis>
